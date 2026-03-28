const modelSelect = document.querySelector("#modelSelect");
const systemPrompt = document.querySelector("#systemPrompt");
const storyIdInput = document.querySelector("#storyIdInput");
const messagesEl = document.querySelector("#messages");
const chatForm = document.querySelector("#chatForm");
const messageInput = document.querySelector("#messageInput");
const sendButton = document.querySelector("#sendButton");
const statusText = document.querySelector("#statusText");

const defaultSystem = "You are a helpful, concise assistant.";
const defaultStoryId = "default-story";
const state = {
  messages: [],
  sending: false,
};

systemPrompt.value = defaultSystem;
storyIdInput.value = localStorage.getItem("storyId") || defaultStoryId;

storyIdInput.addEventListener("change", () => {
  const value = storyIdInput.value.trim() || defaultStoryId;
  storyIdInput.value = value;
  localStorage.setItem("storyId", value);
});

function setStatus(text) {
  statusText.textContent = text;
}

function renderMessages() {
  messagesEl.innerHTML = "";

  if (state.messages.length === 0) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = "Start the conversation with a quick prompt.";
    messagesEl.append(empty);
    return;
  }

  for (const message of state.messages) {
    const item = document.createElement("article");
    item.className = `message message-${message.role}`;

    const label = document.createElement("span");
    label.className = "message-role";
    label.textContent = message.role === "user" ? "You" : "Bot";

    const body = document.createElement("p");
    body.className = "message-body";
    body.textContent = message.content;

    item.append(label, body);
    messagesEl.append(item);
  }

  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function setSending(sending) {
  state.sending = sending;
  sendButton.disabled = sending;
  messageInput.disabled = sending;
  modelSelect.disabled = sending;
  systemPrompt.disabled = sending;
  storyIdInput.disabled = sending;
}

async function loadModels() {
  setStatus("Loading models...");

  try {
    const response = await fetch("/api/models");
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "Could not load models.");
    }

    modelSelect.innerHTML = "";
    for (const model of data.models) {
      const option = document.createElement("option");
      option.value = model;
      option.textContent = model;
      if (model === "qwen2.5:7b") {
        option.selected = true;
      }
      modelSelect.append(option);
    }

    if (!modelSelect.value && data.models.length > 0) {
      modelSelect.value = data.models[0];
    }

    setStatus(`Ready with ${data.models.length} model${data.models.length === 1 ? "" : "s"}.`);
  } catch (error) {
    setStatus(error.message);
  }
}

function appendAssistantPlaceholder() {
  state.messages.push({ role: "assistant", content: "" });
  renderMessages();
}

function updateAssistantMessage(text) {
  const last = state.messages[state.messages.length - 1];
  if (last && last.role === "assistant") {
    last.content = text;
    renderMessages();
  }
}

async function sendMessage(event) {
  event.preventDefault();
  if (state.sending) {
    return;
  }

  const content = messageInput.value.trim();
  if (!content) {
    return;
  }

  state.messages.push({ role: "user", content });
  messageInput.value = "";
  appendAssistantPlaceholder();
  renderMessages();
  setSending(true);
  setStatus("Streaming response...");

  try {
    const response = await fetch("/api/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model: modelSelect.value,
        system: systemPrompt.value.trim() || defaultSystem,
        conversation_id: storyIdInput.value.trim() || defaultStoryId,
        messages: state.messages.filter((message) => message.role === "user" || message.role === "assistant").slice(0, -1),
      }),
    });

    if (!response.ok || !response.body) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.detail || "Chat request failed.");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let assistantText = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) {
        break;
      }

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        if (!line.trim()) {
          continue;
        }

        const eventData = JSON.parse(line);
        if (eventData.type === "chunk") {
          assistantText += eventData.content;
          updateAssistantMessage(assistantText);
        } else if (eventData.type === "error") {
          throw new Error(eventData.content);
        }
      }
    }

    setStatus("Ready.");
  } catch (error) {
    updateAssistantMessage(`Error: ${error.message}`);
    setStatus(error.message);
  } finally {
    setSending(false);
  }
}

chatForm.addEventListener("submit", sendMessage);
renderMessages();
loadModels();
