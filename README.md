# Ollama Chat Bot Example

Small dependency-free terminal chatbot for an Ollama server.

## Run

```bash
python3 chat_bot.py
```

This example defaults to:

- host: `http://192.168.56.1:11434`
- model: `qwen2.5:7b`

You can override either value:

```bash
python3 chat_bot.py --model llama3.1:8b
python3 chat_bot.py --host http://192.168.56.1:11434 --model qwen3:8b
```

Type `exit` or `quit` to stop.
