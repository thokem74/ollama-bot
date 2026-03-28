#!/usr/bin/env python3
"""Minimal terminal chatbot for an Ollama server."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request


DEFAULT_HOST = "http://192.168.56.1:11434"
DEFAULT_MODEL = "qwen2.5:7b"
DEFAULT_SYSTEM = "You are a helpful, concise assistant."


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


def chat(host: str, model: str, messages: list[dict[str, str]]) -> str:
    payload = json.dumps(
        {
            "model": model,
            "messages": messages,
            "stream": False,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{host.rstrip('/')}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {details}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not reach Ollama at {host}: {exc.reason}") from exc

    message = body.get("message", {})
    content = message.get("content")
    if not content:
        raise RuntimeError(f"Unexpected Ollama response: {body}")
    return content


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
        except RuntimeError as exc:
            print(f"bot> error: {exc}", file=sys.stderr)
            messages.pop()
            continue

        messages.append({"role": "assistant", "content": answer})
        print(f"bot> {answer}")


if __name__ == "__main__":
    raise SystemExit(main())
