let sessionId = null;
let isStreaming = false;

const messagesEl = document.getElementById("messages");
const inputEl = document.getElementById("input");
const sendBtn = document.getElementById("send-btn");

// Auto-grow textarea
inputEl.addEventListener("input", () => {
  inputEl.style.height = "auto";
  inputEl.style.height = inputEl.scrollHeight + "px";
});

// Enter to send, Shift+Enter for newline
inputEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    send();
  }
});

sendBtn.addEventListener("click", send);

function setDisabled(disabled) {
  inputEl.disabled = disabled;
  sendBtn.disabled = disabled;
  isStreaming = disabled;
}

function scrollToBottom() {
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function addMessage(role, text) {
  const welcome = messagesEl.querySelector(".welcome");
  if (welcome) welcome.remove();

  const msg = document.createElement("div");
  msg.className = `msg ${role}`;

  const label = document.createElement("div");
  label.className = "msg-label";
  label.textContent = role === "user" ? "You" : "Aimee";

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  if (text) bubble.textContent = text;

  msg.appendChild(label);
  msg.appendChild(bubble);
  messagesEl.appendChild(msg);
  scrollToBottom();
  return { msg, bubble };
}

function addErrorBubble(text) {
  const welcome = messagesEl.querySelector(".welcome");
  if (welcome) welcome.remove();

  const msg = document.createElement("div");
  msg.className = "msg aimee";

  const label = document.createElement("div");
  label.className = "msg-label";
  label.textContent = "Aimee";

  const bubble = document.createElement("div");
  bubble.className = "bubble error";
  bubble.textContent = text;

  msg.appendChild(label);
  msg.appendChild(bubble);
  messagesEl.appendChild(msg);
  scrollToBottom();
}

function setToolLine(bubble, text) {
  let line = bubble.querySelector(".tool-line");
  if (!line) {
    line = document.createElement("div");
    line.className = "tool-line";
    bubble.appendChild(line);
    line.textContent = text;
  } else {
    line.classList.add("fade-out");
    clearTimeout(line._t);
    line._t = setTimeout(() => {
      line.textContent = text;
      line.classList.remove("fade-out");
    }, 200);
  }
  scrollToBottom();
}

function handleSSEEvent(evt, bubble) {
  if (evt.type === "session_id") {
    sessionId = evt.value;

  } else if (evt.type === "token") {
    const line = bubble.querySelector(".tool-line");
    if (line) clearTimeout(line._t);
    bubble.textContent = evt.text;
    scrollToBottom();

  } else if (evt.type === "tool") {
    if (!evt.done) {
      setToolLine(bubble, `⚡ Using ${evt.name}…`);
    }

  } else if (evt.type === "error") {
    bubble.remove();
    addErrorBubble(evt.text || "An error occurred.");
    setDisabled(false);

  } else if (evt.type === "done") {
    setDisabled(false);
  }
}

async function send() {
  const message = inputEl.value.trim();
  if (!message || isStreaming) return;

  inputEl.value = "";
  inputEl.style.height = "auto";
  setDisabled(true);

  addMessage("user", message);

  const msgEl = document.createElement("div");
  msgEl.className = "msg aimee";

  const label = document.createElement("div");
  label.className = "msg-label";
  label.textContent = "Aimee";

  const bubble = document.createElement("div");
  bubble.className = "bubble";

  msgEl.appendChild(label);
  msgEl.appendChild(bubble);
  messagesEl.appendChild(msgEl);
  scrollToBottom();

  setToolLine(bubble, "Aimee is thinking…");

  try {
    const res = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, session_id: sessionId }),
    });

    if (!res.ok) {
      bubble.textContent = "Something went wrong. Please try again.";
      setDisabled(false);
      return;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop();

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const raw = line.slice(6).trim();
        if (!raw) continue;

        let evt;
        try { evt = JSON.parse(raw); } catch { continue; }

        handleSSEEvent(evt, bubble);
      }
    }
  } catch (err) {
    bubble.textContent = "Connection error. Please try again.";
    setDisabled(false);
  }
}

// Browser ignores this block; Jest picks it up for unit testing
if (typeof module !== "undefined") {
  module.exports = { addMessage, addErrorBubble, setDisabled, handleSSEEvent };
}
