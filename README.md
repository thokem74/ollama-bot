# Ollama Chat Bot Example

Small Ollama chatbot project with:

- a FastAPI web UI
- a reusable Python Ollama client
- the original terminal chat example

Defaults:

- host: `http://192.168.56.1:11434`
- model: `qwen2.5:7b`

You can override the host with `OLLAMA_HOST`.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run The Web UI

```bash
uvicorn app:app --reload
```

Then open `http://127.0.0.1:8000`.

or, if port 8000 already used

```bash
uvicorn app:app --reload --port 8017
```

Then open `http://127.0.0.1:8017`.

## Run The Terminal Bot

```bash
python3 chat_bot.py
```

You can switch models in either UI. For the terminal version:

```bash
python3 chat_bot.py --model llama3.1:8b
python3 chat_bot.py --host http://192.168.56.1:11434 --model qwen3:8b
```

Type `exit` or `quit` to stop the terminal bot.
