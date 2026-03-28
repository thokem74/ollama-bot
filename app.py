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


BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Ollama Chat Bot")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    model: str = Field(min_length=1)
    system: str = Field(default=DEFAULT_SYSTEM)
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
    upstream_messages = [{"role": "system", "content": request.system.strip() or DEFAULT_SYSTEM}]
    upstream_messages.extend(message.model_dump() for message in request.messages)

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
        if first_chunk is not None:
            yield json.dumps({"type": "chunk", "content": first_chunk}) + "\n"

        try:
            for chunk in iterator:
                yield json.dumps({"type": "chunk", "content": chunk}) + "\n"
        except OllamaError as exc:
            yield json.dumps({"type": "error", "content": str(exc)}) + "\n"
            return

        yield json.dumps({"type": "done"}) + "\n"

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")
