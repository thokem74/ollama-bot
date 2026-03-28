#!/usr/bin/env python3
"""FastAPI web UI for chatting with Ollama."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ollama_client import DEFAULT_HOST, DEFAULT_SYSTEM, OllamaError, list_models, stream_chat
from story_memory import (
    DEFAULT_STORY_ID,
    build_story_messages,
    compact_story_state,
    load_story_state,
    save_story_state,
    sanitize_story_id,
    trim_recent_messages,
)


BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Ollama Chat Bot")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    model: str = Field(min_length=1)
    system: str = Field(default=DEFAULT_SYSTEM)
    conversation_id: str = Field(default=DEFAULT_STORY_ID, min_length=1)
    messages: list[ChatMessage]


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.get("/api/models")
async def api_models() -> dict[str, list[str]]:
    try:
        return {"models": list_models(DEFAULT_HOST)}
    except OllamaError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/chat/stream")
async def api_chat_stream(request: ChatRequest) -> StreamingResponse:
    messages = [message.model_dump() for message in request.messages if message.content.strip()]
    if not messages:
        raise HTTPException(status_code=400, detail="At least one user message is required.")
    if messages[-1]["role"] != "user":
        raise HTTPException(status_code=400, detail="The latest message must be a user message.")

    conversation_id = sanitize_story_id(request.conversation_id)
    story_state = load_story_state(conversation_id)
    latest_user_input = messages[-1]["content"].strip()
    recent_messages = trim_recent_messages(messages[:-1])
    upstream_messages = build_story_messages(
        system_prompt=request.system.strip() or DEFAULT_SYSTEM,
        story_state=story_state,
        recent_messages=recent_messages,
        latest_user_input=latest_user_input,
    )

    try:
        iterator = stream_chat(
            messages=upstream_messages,
            model=request.model,
            host=DEFAULT_HOST,
        )
        first_chunk = next(iterator, None)
    except OllamaError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    def event_stream():
        assistant_chunks: list[str] = []
        if first_chunk is not None:
            assistant_chunks.append(first_chunk)
            yield json.dumps({"type": "chunk", "content": first_chunk}) + "\n"

        try:
            for chunk in iterator:
                assistant_chunks.append(chunk)
                yield json.dumps({"type": "chunk", "content": chunk}) + "\n"
        except OllamaError as exc:
            yield json.dumps({"type": "error", "content": str(exc)}) + "\n"
            return

        assistant_text = "".join(assistant_chunks)
        if assistant_text.strip():
            try:
                compacted_state = compact_story_state(
                    host=DEFAULT_HOST,
                    model=request.model,
                    story_id=conversation_id,
                    previous_state=story_state,
                    user_input=latest_user_input,
                    assistant_reply=assistant_text,
                )
            except OllamaError:
                pass
            else:
                save_story_state(conversation_id, compacted_state)

        yield json.dumps({"type": "done"}) + "\n"

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")
