const chatLog = document.getElementById("chat-log");
const traceLog = document.getElementById("trace-log");
const statusText = document.getElementById("status-text");
const modelSelect = document.getElementById("model-select");
const sessionInput = document.getElementById("session-input");
const newSessionBtn = document.getElementById("new-session-btn");
const loadSessionBtn = document.getElementById("load-session-btn");
const form = document.getElementById("chat-form");
const userInput = document.getElementById("user-input");
const streamToggle = document.getElementById("stream-toggle");
const sendBtn = document.getElementById("send-btn");

const LOCAL_KEY = "ollama_fastapi_session_id";

const state = {
  sessionId: "",
  running: false,
};

function timestamp() {
  return new Date().toLocaleTimeString();
}

function setStatus(text) {
  statusText.textContent = text;
}

function addTrace(text, level = "info") {
  const item = document.createElement("div");
  item.className = `trace-item ${level === "error" ? "error" : ""}`.trim();
  item.textContent = `[${timestamp()}] ${text}`;
  traceLog.appendChild(item);
  traceLog.scrollTop = traceLog.scrollHeight;
}

function addMessage(role, content) {
  const node = document.createElement("div");
  node.className = `message ${role}`;
  node.textContent = content;
  chatLog.appendChild(node);
  chatLog.scrollTop = chatLog.scrollHeight;
  return node;
}

function setRunning(running) {
  state.running = running;
  sendBtn.disabled = running;
  newSessionBtn.disabled = running;
  loadSessionBtn.disabled = running;
}

async function createSession() {
  const resp = await fetch("/chat/sessions", { method: "POST" });
  if (!resp.ok) {
    throw new Error(`Create session failed: ${resp.status}`);
  }
  const data = await resp.json();
  state.sessionId = data.session_id;
  sessionInput.value = state.sessionId;
  localStorage.setItem(LOCAL_KEY, state.sessionId);
  addTrace(`New session created: ${state.sessionId}`);
}

async function loadSessionHistory(sessionId) {
  chatLog.innerHTML = "";
  const resp = await fetch(`/chat/sessions/${encodeURIComponent(sessionId)}`);
  if (!resp.ok) {
    throw new Error(`Load session failed: ${resp.status}`);
  }
  const data = await resp.json();
  const messages = data.messages || [];
  if (messages.length === 0) {
    addMessage("system", "Session loaded. No history yet.");
    return;
  }
  for (const msg of messages) {
    addMessage(msg.role, msg.content || "");
  }
  addTrace(`Loaded ${messages.length} messages from ${sessionId}`);
}

async function refreshModels() {
  const resp = await fetch("/models");
  if (!resp.ok) {
    throw new Error(`Model list failed: ${resp.status}`);
  }
  const data = await resp.json();
  const models = data.models || [];
  modelSelect.innerHTML = "";
  for (const model of models) {
    const option = document.createElement("option");
    option.value = model;
    option.textContent = model;
    modelSelect.appendChild(option);
  }
  addTrace(`Loaded ${models.length} models`);
}

function setFallbackModelOption() {
  modelSelect.innerHTML = "";
  const option = document.createElement("option");
  option.value = "";
  option.textContent = "(use server default model)";
  modelSelect.appendChild(option);
}

async function sendNonStream(payload, assistantNode) {
  const startedAt = performance.now();
  const resp = await fetch("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!resp.ok) {
    throw new Error(`Chat failed: ${resp.status} ${await resp.text()}`);
  }
  const body = await resp.json();
  assistantNode.textContent = body.content || "";
  const elapsed = Math.round(performance.now() - startedAt);
  addTrace(`Non-stream done in ${elapsed} ms, model=${body.model}`);
}

function parseSseChunk(chunk) {
  const lines = chunk.split(/\r?\n/);
  let event = "message";
  const dataLines = [];
  for (const line of lines) {
    if (line.startsWith("event:")) {
      event = line.slice("event:".length).trim();
      continue;
    }
    if (line.startsWith("data:")) {
      dataLines.push(line.slice("data:".length).trimStart());
    }
  }
  return { event, data: dataLines.join("\n") };
}

function popSseBlock(buffer) {
  const crlfIndex = buffer.indexOf("\r\n\r\n");
  const lfIndex = buffer.indexOf("\n\n");

  if (crlfIndex === -1 && lfIndex === -1) {
    return null;
  }

  if (crlfIndex !== -1 && (lfIndex === -1 || crlfIndex < lfIndex)) {
    return {
      block: buffer.slice(0, crlfIndex),
      rest: buffer.slice(crlfIndex + 4),
    };
  }

  return {
    block: buffer.slice(0, lfIndex),
    rest: buffer.slice(lfIndex + 2),
  };
}

async function sendStream(payload, assistantNode) {
  const startedAt = performance.now();
  const resp = await fetch("/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!resp.ok || !resp.body) {
    throw new Error(`Stream failed: ${resp.status} ${await resp.text()}`);
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let firstTokenAt = 0;
  let tokenCount = 0;
  let assistant = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    while (true) {
      const parsed = popSseBlock(buffer);
      if (!parsed) break;

      const block = parsed.block.trim();
      buffer = parsed.rest;
      if (!block) continue;

      const { event, data } = parseSseChunk(block);
      if (event === "token") {
        if (!firstTokenAt) {
          firstTokenAt = performance.now();
          addTrace(`First token in ${Math.round(firstTokenAt - startedAt)} ms`);
        }
        tokenCount += 1;
        assistant += data;
        assistantNode.textContent = assistant;
        chatLog.scrollTop = chatLog.scrollHeight;
      } else if (event === "error") {
        throw new Error(data || "stream error");
      } else if (event === "done") {
        const elapsed = Math.round(performance.now() - startedAt);
        addTrace(`Stream done in ${elapsed} ms, chunks=${tokenCount}`);
      }
    }
  }
}

async function runTask(query) {
  const payload = {
    session_id: state.sessionId,
    model: modelSelect.value || null,
    temperature: 0.7,
    messages: [{ role: "user", content: query }],
  };

  addMessage("user", query);
  const assistantNode = addMessage("assistant", "");
  setStatus("Running...");
  setRunning(true);
  addTrace(`Task started | session=${state.sessionId}`);

  try {
    if (streamToggle.checked) {
      await sendStream(payload, assistantNode);
    } else {
      await sendNonStream(payload, assistantNode);
    }
    setStatus("Done");
  } catch (err) {
    assistantNode.textContent = "";
    addMessage("system", `Error: ${err.message}`);
    addTrace(err.message, "error");
    setStatus("Failed");
  } finally {
    setRunning(false);
  }
}

async function bootstrap() {
  setStatus("Bootstrapping...");
  setRunning(true);
  try {
    let modelLoadFailed = false;
    try {
      await refreshModels();
    } catch (err) {
      modelLoadFailed = true;
      setFallbackModelOption();
      addTrace(err.message, "error");
    }

    const cachedSession = localStorage.getItem(LOCAL_KEY);
    if (cachedSession) {
      state.sessionId = cachedSession;
      sessionInput.value = cachedSession;
      await loadSessionHistory(cachedSession);
      addTrace(`Resume cached session: ${cachedSession}`);
    } else {
      await createSession();
      addMessage("system", "Session is ready. Type a query and run.");
    }
    setStatus(modelLoadFailed ? "Ready (fallback model)" : "Ready");
  } catch (err) {
    addTrace(err.message, "error");
    addMessage("system", `Bootstrap failed: ${err.message}`);
    setStatus("Failed");
  } finally {
    setRunning(false);
  }
}

newSessionBtn.addEventListener("click", async () => {
  if (state.running) return;
  setRunning(true);
  try {
    await createSession();
    chatLog.innerHTML = "";
    addMessage("system", "New session created. History starts now.");
    setStatus("Ready");
  } catch (err) {
    addTrace(err.message, "error");
    setStatus("Failed");
  } finally {
    setRunning(false);
  }
});

loadSessionBtn.addEventListener("click", async () => {
  if (state.running) return;
  const sessionId = sessionInput.value.trim();
  if (!sessionId) return;
  setRunning(true);
  try {
    state.sessionId = sessionId;
    localStorage.setItem(LOCAL_KEY, sessionId);
    await loadSessionHistory(sessionId);
    setStatus("Ready");
  } catch (err) {
    addTrace(err.message, "error");
    setStatus("Failed");
  } finally {
    setRunning(false);
  }
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (state.running) return;
  const query = userInput.value.trim();
  if (!query) return;
  userInput.value = "";
  await runTask(query);
});

bootstrap();
