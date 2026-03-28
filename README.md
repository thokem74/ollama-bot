# Ollama Chat Bot Example

Small Ollama chatbot project with:

- a FastAPI web UI
- a reusable Python Ollama client
- persistent storyteller memory for long-running story chats
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

## Storyteller Memory

The bot now keeps a compact story memory on disk and sends that story info to the
model on every user turn. This lets longer stories stay coherent without sending
an ever-growing full transcript.

- story files are stored in `stories/`
- each story is saved as `<story-id>.json`
- the saved memory includes:
  - story summary
  - characters
  - locations
  - open plot threads
  - important facts and rules
  - a compact list of recent turns

### Terminal Usage

```bash
python3 chat_bot.py --story-id forest-chronicle
```

If you omit `--story-id`, the terminal bot uses `default-story`.

### Web Usage

The web UI includes a `Story ID` field. Reuse the same ID to continue a story, or
change it to start a different one.

### Reset A Story

Delete the matching JSON file in `stories/` to reset that story.
