#!/usr/bin/env python3
"""Shared Ollama client helpers for CLI and web UI."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Iterator


DEFAULT_HOST = os.environ.get("OLLAMA_HOST", "http://192.168.56.1:11434")
DEFAULT_MODEL = "qwen2.5:7b"
DEFAULT_SYSTEM = "You are a helpful, concise assistant."


class OllamaError(RuntimeError):
    """Raised when the Ollama API returns an error or cannot be reached."""


def _request(
    host: str,
    path: str,
    payload: dict | None = None,
    timeout: int = 300,
):
    data = None
    headers: dict[str, str] = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(
        f"{host.rstrip('/')}{path}",
        data=data,
        headers=headers,
        method="POST" if payload is not None else "GET",
    )

    try:
        return urllib.request.urlopen(request, timeout=timeout)
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise OllamaError(f"HTTP {exc.code}: {details}") from exc
    except urllib.error.URLError as exc:
        raise OllamaError(f"Could not reach Ollama at {host}: {exc.reason}") from exc


def list_models(host: str = DEFAULT_HOST) -> list[str]:
    with _request(host, "/api/tags", timeout=30) as response:
        body = json.loads(response.read().decode("utf-8"))
    return [model["name"] for model in body.get("models", []) if model.get("name")]


def chat(
    messages: list[dict[str, str]],
    model: str = DEFAULT_MODEL,
    host: str = DEFAULT_HOST,
) -> str:
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
    }
    with _request(host, "/api/chat", payload=payload) as response:
        body = json.loads(response.read().decode("utf-8"))

    message = body.get("message", {})
    content = message.get("content")
    if not content:
        raise OllamaError(f"Unexpected Ollama response: {body}")
    return content


def stream_chat(
    messages: list[dict[str, str]],
    model: str = DEFAULT_MODEL,
    host: str = DEFAULT_HOST,
) -> Iterator[str]:
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
    }
    with _request(host, "/api/chat", payload=payload) as response:
        for raw_line in response:
            if not raw_line:
                continue
            line = raw_line.decode("utf-8").strip()
            if not line:
                continue

            try:
                chunk = json.loads(line)
            except json.JSONDecodeError as exc:
                raise OllamaError(f"Invalid streaming response from Ollama: {line}") from exc

            if chunk.get("error"):
                raise OllamaError(str(chunk["error"]))

            message = chunk.get("message", {})
            content = message.get("content")
            if content:
                yield content

            if chunk.get("done"):
                return
