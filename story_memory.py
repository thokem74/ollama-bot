#!/usr/bin/env python3
"""Persistent storyteller memory helpers."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from ollama_client import OllamaError, chat


BASE_DIR = Path(__file__).resolve().parent
STORY_DIR = BASE_DIR / "stories"
DEFAULT_STORY_ID = "default-story"
RECENT_TURNS_LIMIT = 6
RECENT_MESSAGES_LIMIT = 8
LIST_LIMIT = 12
TEXT_LIMIT = 2400

COMPACTION_PROMPT = """You are a story memory engine.
Rewrite the ongoing story into compact JSON for long-term continuity.

Return JSON only with this exact schema:
{
  "summary": "string",
  "characters": ["string"],
  "locations": ["string"],
  "open_threads": ["string"],
  "facts": ["string"],
  "recent_turns": [
    {
      "user": "string",
      "assistant": "string"
    }
  ]
}

Rules:
- Keep the summary concise but useful.
- Keep only important named characters, locations, unresolved threads, and hard facts.
- Remove repetition and incidental chatter.
- Keep at most 6 recent_turns.
- recent_turns must describe the latest conversation beats, oldest to newest.
- Preserve canonical names and story rules when they matter.
- Return valid JSON and nothing else.
"""


def sanitize_story_id(raw_story_id: str | None) -> str:
    raw = (raw_story_id or "").strip() or DEFAULT_STORY_ID
    sanitized = re.sub(r"[^a-zA-Z0-9_-]+", "-", raw).strip("-").lower()
    return sanitized or DEFAULT_STORY_ID


def story_path(story_id: str | None) -> Path:
    STORY_DIR.mkdir(parents=True, exist_ok=True)
    return STORY_DIR / f"{sanitize_story_id(story_id)}.json"


def _default_story_state(story_id: str) -> dict:
    return {
        "story_id": story_id,
        "summary": "",
        "characters": [],
        "locations": [],
        "open_threads": [],
        "facts": [],
        "recent_turns": [],
        "updated_at": None,
    }


def _clean_text(value: object, limit: int = 400) -> str:
    text = str(value or "").strip()
    text = re.sub(r"\s+", " ", text)
    return text[:limit]


def _clean_list(values: object, *, item_limit: int = 180, max_items: int = LIST_LIMIT) -> list[str]:
    if not isinstance(values, list):
        return []

    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = _clean_text(value, limit=item_limit)
        if not item:
            continue
        key = item.casefold()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(item)
        if len(cleaned) >= max_items:
            break
    return cleaned


def _clean_recent_turns(turns: object) -> list[dict[str, str]]:
    if not isinstance(turns, list):
        return []

    cleaned: list[dict[str, str]] = []
    for turn in turns[-RECENT_TURNS_LIMIT:]:
        if not isinstance(turn, dict):
            continue
        user = _clean_text(turn.get("user"), limit=500)
        assistant = _clean_text(turn.get("assistant"), limit=700)
        if not user and not assistant:
            continue
        cleaned.append({"user": user, "assistant": assistant})
    return cleaned


def normalize_story_state(story_id: str | None, data: dict | None = None) -> dict:
    normalized_id = sanitize_story_id(story_id)
    story = _default_story_state(normalized_id)
    payload = data or {}
    if not isinstance(payload, dict):
        return story

    story["summary"] = _clean_text(payload.get("summary"), limit=TEXT_LIMIT)
    story["characters"] = _clean_list(payload.get("characters"))
    story["locations"] = _clean_list(payload.get("locations"))
    story["open_threads"] = _clean_list(payload.get("open_threads"))
    story["facts"] = _clean_list(payload.get("facts"))
    story["recent_turns"] = _clean_recent_turns(payload.get("recent_turns"))
    story["updated_at"] = payload.get("updated_at")
    return story


def load_story_state(story_id: str | None) -> dict:
    normalized_id = sanitize_story_id(story_id)
    path = story_path(normalized_id)
    if not path.exists():
        return _default_story_state(normalized_id)

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _default_story_state(normalized_id)

    return normalize_story_state(normalized_id, payload)


def save_story_state(story_id: str | None, state: dict) -> None:
    normalized = normalize_story_state(story_id, state)
    normalized["updated_at"] = datetime.now(timezone.utc).isoformat()
    path = story_path(normalized["story_id"])
    path.write_text(json.dumps(normalized, indent=2), encoding="utf-8")


def format_story_info(state: dict) -> str:
    def section(title: str, values: list[str]) -> str:
        if not values:
            return f"{title}: none recorded."
        bullets = "\n".join(f"- {item}" for item in values)
        return f"{title}:\n{bullets}"

    summary = state.get("summary") or "No story summary recorded yet."
    recent_turns = state.get("recent_turns") or []
    if recent_turns:
        recent_text = "\n".join(
            f"- User: {turn['user']}\n  Assistant: {turn['assistant']}" for turn in recent_turns
        )
    else:
        recent_text = "- No prior turns saved."

    return "\n\n".join(
        [
            "Use this compact story memory for continuity. Treat it as the authoritative long-term story record.",
            f"Story ID: {state.get('story_id', DEFAULT_STORY_ID)}",
            f"Summary:\n{summary}",
            section("Important characters", state.get("characters", [])),
            section("Locations", state.get("locations", [])),
            section("Open plot threads", state.get("open_threads", [])),
            section("Important facts and rules", state.get("facts", [])),
            f"Recent turns:\n{recent_text}",
        ]
    )


def trim_recent_messages(messages: list[dict[str, str]], max_messages: int = RECENT_MESSAGES_LIMIT) -> list[dict[str, str]]:
    filtered = [
        {"role": message["role"], "content": message["content"]}
        for message in messages
        if message.get("role") in {"user", "assistant"} and message.get("content")
    ]
    return filtered[-max_messages:]


def build_story_messages(
    system_prompt: str,
    story_state: dict,
    recent_messages: list[dict[str, str]],
    latest_user_input: str,
) -> list[dict[str, str]]:
    messages = [
        {"role": "system", "content": system_prompt.strip()},
        {"role": "system", "content": format_story_info(story_state)},
    ]
    messages.extend(trim_recent_messages(recent_messages))
    messages.append({"role": "user", "content": latest_user_input})
    return messages


def _recent_turns_with_latest(state: dict, user_input: str, assistant_reply: str) -> list[dict[str, str]]:
    recent_turns = deepcopy(state.get("recent_turns", []))
    recent_turns.append(
        {
            "user": _clean_text(user_input, limit=500),
            "assistant": _clean_text(assistant_reply, limit=700),
        }
    )
    return _clean_recent_turns(recent_turns)


def _extract_json_object(raw_text: str) -> dict | None:
    text = raw_text.strip()
    if not text:
        return None

    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None

    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def compact_story_state(
    *,
    host: str,
    model: str,
    story_id: str | None,
    previous_state: dict,
    user_input: str,
    assistant_reply: str,
) -> dict:
    if not assistant_reply.strip():
        raise OllamaError("Assistant reply was empty; skipping story compaction.")

    normalized_id = sanitize_story_id(story_id)
    candidate_state = normalize_story_state(normalized_id, previous_state)
    candidate_state["recent_turns"] = _recent_turns_with_latest(candidate_state, user_input, assistant_reply)

    compaction_messages = [
        {"role": "system", "content": COMPACTION_PROMPT},
        {
            "role": "user",
            "content": json.dumps(
                {
                    "story_id": normalized_id,
                    "existing_story_memory": candidate_state,
                    "latest_user_input": user_input,
                    "latest_assistant_reply": assistant_reply,
                },
                ensure_ascii=True,
                indent=2,
            ),
        },
    ]

    compacted_raw = chat(messages=compaction_messages, model=model, host=host)
    compacted_payload = _extract_json_object(compacted_raw)
    if compacted_payload is None:
        raise OllamaError("Story compaction did not return valid JSON.")

    compacted_state = normalize_story_state(normalized_id, compacted_payload)
    compacted_state["recent_turns"] = _recent_turns_with_latest(compacted_state, user_input, assistant_reply)
    return compacted_state
