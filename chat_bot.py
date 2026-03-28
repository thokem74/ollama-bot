#!/usr/bin/env python3
"""Minimal terminal chatbot for an Ollama server."""

from __future__ import annotations

import argparse
import sys

from ollama_client import DEFAULT_HOST, DEFAULT_MODEL, DEFAULT_SYSTEM, OllamaError, chat


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
    return parser.parse_args()
def main() -> int:
    args = parse_args()
    messages: list[dict[str, str]] = [{"role": "system", "content": args.system}]

    print(f"Connected bot config: host={args.host} model={args.model}")
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

        messages.append({"role": "user", "content": user_input})

        try:
            answer = chat(args.host, args.model, messages)
        except OllamaError as exc:
            print(f"bot> error: {exc}", file=sys.stderr)
            messages.pop()
            continue

        messages.append({"role": "assistant", "content": answer})
        print(f"bot> {answer}")


if __name__ == "__main__":
    raise SystemExit(main())
