# Aimee — AI Professor

A web chat application powered by **Anthropic Managed Agents**. Aimee is a Claude-backed AI professor that answers questions about a mounted knowledge base of markdown files. The agent runs inside a per-session container hosted by Anthropic, reads files using built-in tools (glob, read, grep), and streams lifecycle events to the frontend in real time.

> **No RAG.** This project does not use retrieval-augmented generation or any vector/embedding pipeline. The agent reads files directly using its built-in `glob`, `read`, and `grep` tools — it decides which files to open based on the user's question and the instructions in its system prompt.

---

## How it works

```
Browser  ──POST /chat──►  Flask (api/index.py)
                               │
                               ▼
                         run_session.py
                               │
                    ┌──────────┴──────────┐
                    ▼                     ▼
          sessions.events.stream     sessions.events.send
                    │                     │
                    └────── Anthropic ─────┘
                           Managed Agent
                               │
                        /workspace/Aimee-AI/
                          (mounted KB files)
```

1. The browser sends a message to `/chat`.
2. Flask calls `stream_events()` in `run_session.py`, which opens an SSE stream to the Anthropic sessions API **before** sending the user message (to avoid missing early events).
3. The agent uses built-in tools (`glob`, `read`, `grep`) to find relevant knowledge-base files, then returns a response.
4. Lifecycle events (tool calls, status changes, errors) are forwarded to the browser over SSE as they arrive. The final text response arrives in a single `agent.message` event.
5. The frontend renders the response as Markdown + LaTeX (KaTeX).

---

## Setup

### Prerequisites

- Python 3.11+
- Node.js 18+ (for frontend tests only)
- An Anthropic API key with Managed Agents access

### Install

```bash
pip install -r requirements.txt
npm install          # only needed for frontend tests
```

### Environment variable

Create a `.env` file in the project root:

```
ANTHROPIC_API_KEY=sk-ant-...
```

---

## Three-phase workflow

Run these in order the **first time**. After that, only step 3 is needed for each session.

### 1. Create the agent and environment (once)

```bash
python scripts/setup_agent.py
```

Creates a reusable agent (with system prompt and tools) and a cloud environment on Anthropic's infrastructure. Writes `aimee_agent_config.json`.

### 2. Upload the knowledge base (once per KB change)

```bash
python scripts/upload_kb.py
```

Uploads every `.md` file from the configured `KB_FOLDER` to the Anthropic Files API and records the file IDs and mount paths in `aimee_kb_files.json`. Files are mounted at `/workspace/Aimee-AI/` inside each session container.

To change the knowledge base folder, edit `KB_FOLDER` in `scripts/upload_kb.py`.

### 3. Run the web app

```bash
python api/index.py
```

Opens at `http://localhost:5000`.

### CLI alternative

```bash
python run_session.py "What does chapter 2 cover?"
```

---

## API endpoints

### `GET /`

Returns the chat UI.

**Response:** `200 OK` — `text/html`

---

### `POST /chat`

Sends a user message to the agent and streams lifecycle events back as SSE.

**Request body** (`application/json`):

| Field | Type | Required | Description |
|---|---|---|---|
| `message` | string | Yes | The user's question or message |
| `session_id` | string | No | Existing session ID to continue a conversation. Omit to start a new session. |

**Response:** `200 OK` — `text/event-stream`

Each line is a Server-Sent Event in the format `data: {json}\n\n`. Event types:

| `type` | Fields | When it fires |
|---|---|---|
| `session_id` | `value: string` | First event of a new session — contains the session ID to pass back on subsequent requests |
| `token` | `text: string` | The agent's complete text response (arrives once, at the end) |
| `tool` | `name: string`, `done: bool` | Tool activity — `done: false` when a tool starts, `done: true` when it finishes |
| `error` | `text: string` | Agent or API error — stream ends after this |
| `done` | _(no extra fields)_ | Always the final event, signals the stream is complete |

**Error responses:**

| Status | Condition |
|---|---|
| `400 Bad Request` | `message` field is missing or empty |

**Example request:**

```bash
curl -X POST http://localhost:5000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Explain eigenvalues"}' \
  --no-buffer
```

**Example SSE stream:**

```
data: {"type": "session_id", "value": "sess_01abc..."}

data: {"type": "tool", "name": "glob", "done": false}

data: {"type": "tool", "name": "glob", "done": true}

data: {"type": "tool", "name": "read", "done": false}

data: {"type": "tool", "name": "read", "done": true}

data: {"type": "token", "text": "An eigenvalue \\(\\lambda\\) satisfies..."}

data: {"type": "done"}
```

---

## Running tests

```bash
# Backend — 22 tests (pytest)
pytest tests/ -v

# Frontend — 16 tests (Jest + jsdom)
npm run test:frontend
```

---

## Project structure

```
api/index.py              Flask app — SSE endpoint (Vercel entry point)
run_session.py            Shared session core + CLI entry point
scripts/
  setup_agent.py          One-time: creates agent + environment
  upload_kb.py            One-time: uploads KB files to Anthropic Files API
static/
  script.js               Frontend — SSE parsing, Markdown/LaTeX rendering
  style.css               Styles
templates/
  index.html              Chat UI (loads KaTeX + marked.js from CDN)
tests/
  conftest.py             pytest fixtures (Flask test client, temp config files)
  test_api.py             Flask route tests (7 tests)
  test_session.py         stream_events() unit tests (15 tests)
  test_script.test.js     Frontend DOM + SSE event tests (16 tests)
docs/
  STREAM.md               Anthropic session event stream reference
  TOOLS.md                Built-in agent tool reference
  FILES.md                Files API reference
  SKILLS.md               Skills reference
```

### Runtime files (generated, not committed)

| File | Contents |
|---|---|
| `aimee_agent_config.json` | `agent_id`, `agent_version`, `environment_id` |
| `aimee_kb_files.json` | Array of `{type, file_id, mount_path}` for each uploaded `.md` file |

---

## Agent configuration

The agent is created once with a fixed system prompt and toolset defined in `scripts/setup_agent.py`. To update the system prompt or tools:

1. Edit `scripts/setup_agent.py`
2. Call `client.beta.agents.update(agent_id, ...)` rather than creating a new agent — each update bumps the version
3. Update `agent_version` in `aimee_agent_config.json` to pin to the new version (or remove it to always use latest)

The agent has access to the full `agent_toolset_20260401` (glob, read, write, edit, grep, bash, web search) with `always_allow` permission policy — no approval gates.

---

## Frontend rendering

Aimee's responses are rendered as Markdown (via [marked.js](https://marked.js.org/)) with LaTeX math support (via [KaTeX](https://katex.org/)).

**Supported LaTeX delimiters:**

| Syntax | Mode |
|---|---|
| `\( ... \)` | Inline math |
| `\[ ... \]` | Display (block) math |
| `$ ... $` | Inline math |
| `$$ ... $$` | Display math |

The system prompt instructs the agent to use `\( ... \)` and `\[ ... \]` delimiters.
