#!/usr/bin/env python3
"""Minimal terminal chatbot for an Ollama server."""

from __future__ import annotations

import argparse
import sys

from ollama_client import DEFAULT_HOST, DEFAULT_MODEL, DEFAULT_SYSTEM, OllamaError, chat
from story_memory import (
    DEFAULT_STORY_ID,
    build_story_messages,
    compact_story_state,
    load_story_state,
    save_story_state,
    sanitize_story_id,
    trim_recent_messages,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Small Ollama chat bot example")
    parser.add_argument(
        "--host",
        default=DEFAULT_HOST,
        help=f"Ollama base URL (default: {DEFAULT_HOST})",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Model name to use (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--system",
        default=DEFAULT_SYSTEM,
        help="Optional system prompt",
    )
    parser.add_argument(
        "--story-id",
        default=DEFAULT_STORY_ID,
        help=f"Story memory ID to load and persist (default: {DEFAULT_STORY_ID})",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    story_id = sanitize_story_id(args.story_id)
    messages: list[dict[str, str]] = []

    print(f"Connected bot config: host={args.host} model={args.model} story_id={story_id}")
    print("Type 'exit' or 'quit' to stop.")

    while True:
        try:
            user_input = input("\nyou> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nbye")
            return 0

        if not user_input:
            continue

        if user_input.lower() in {"exit", "quit"}:
            print("bye")
            return 0

        story_state = load_story_state(story_id)
        upstream_messages = build_story_messages(
            system_prompt=args.system or DEFAULT_SYSTEM,
            story_state=story_state,
            recent_messages=messages,
            latest_user_input=user_input,
        )

        try:
            answer = chat(messages=upstream_messages, model=args.model, host=args.host)
        except OllamaError as exc:
            print(f"bot> error: {exc}", file=sys.stderr)
            continue

        messages.append({"role": "user", "content": user_input})
        messages.append({"role": "assistant", "content": answer})
        messages = trim_recent_messages(messages)

        try:
            compacted_state = compact_story_state(
                host=args.host,
                model=args.model,
                story_id=story_id,
                previous_state=story_state,
                user_input=user_input,
                assistant_reply=answer,
            )
        except OllamaError as exc:
            print(f"bot> warning: could not update story memory: {exc}", file=sys.stderr)
        else:
            save_story_state(story_id, compacted_state)

        print(f"bot> {answer}")


if __name__ == "__main__":
    raise SystemExit(main())
