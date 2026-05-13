# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project does

This is a **Claude Managed Agents** pipeline that mounts a local folder of markdown files into a per-session container so an agent (Aimee) can answer questions about them. It uses the Anthropic Python SDK's beta managed-agents surface (`client.beta.agents`, `client.beta.environments`, `client.beta.sessions`, `client.beta.files`).

## Required environment variable

```
ANTHROPIC_API_KEY=<your key>
```

## Three-phase workflow

Run these in order the first time, then only the last one on subsequent invocations.

```bash
# 1. Create the reusable agent + environment (once)
python scripts/setup_agent.py

# 2. Upload KB markdown files (once per KB change)
python scripts/upload_kb.py

# 3. Start a session and ask a question (CLI)
python run_session.py "What does chapter 2 cover?"
```

`scripts/setup_agent.py` writes `aimee_agent_config.json` (agent ID + version + environment ID).  
`scripts/upload_kb.py` writes `aimee_kb_files.json` (list of `{type, file_id, mount_path}` dicts).  
`run_session.py` reads both JSON files at runtime — no re-upload, no re-creation.

## Running tests

```bash
# Backend (pytest)
pytest tests/ -v

# Frontend (Jest)
npm install
npm run test:frontend
```

## Architecture

### Shared core: `run_session.py`
`run_session.py` is the single source of truth for session creation and event streaming. It exports `stream_events(message, session_id=None)` which yields transport-neutral event dicts. Both the web app (`api/index.py`) and the CLI entry point consume this same function — no duplication.

### Managed agents constraint
`model`, `system`, and `tools` belong on the **agent object**, never on the session. Sessions are thin — they only accept an `agent` pointer and optional `resources`. This is why setup and runtime are split.

### File mounting
KB files are uploaded to the Anthropic Files API (`client.beta.files.upload`) and attached to each session as resources with explicit `mount_path` values under `/workspace/Aimee-AI/`. The agent reads them using its built-in `read`/`glob` tools.

### Stream-first pattern
The SSE stream is opened **before** `events.send` is called. This prevents missing early events (the stream doesn't replay history — it only delivers events emitted after it opens).

### Session idle-break logic
`session.status_idle` always breaks the loop. `session.status_rescheduled` falls through silently (stream continues). The old `requires_action` check was removed — it never fires with `always_allow` permission policy.

## Key files produced at runtime

| File | Contents |
|---|---|
| `aimee_agent_config.json` | `agent_id`, `agent_version`, `environment_id` |
| `aimee_kb_files.json` | Array of `{type, file_id, mount_path}` for each uploaded `.md` file |

## Directory layout

```
api/index.py          Web app (Vercel entry point — path must not change)
run_session.py        Shared core + CLI entry point
scripts/              One-time setup scripts (setup_agent, upload_kb)
static/               CSS + JS frontend
templates/            HTML template
tests/                pytest (backend) + Jest (frontend) test suites
docs/                 Reference docs (SKILLS, STREAM, FILES, TOOLS)
```

## Changing the knowledge base folder

Edit `KB_FOLDER` in `scripts/upload_kb.py` to point at a different directory.

## Updating the agent

To change the system prompt or tools, edit `scripts/setup_agent.py` and call `client.beta.agents.update(agent_id, ...)` rather than creating a new agent. Each update bumps the version; pin the version in `aimee_agent_config.json` for reproducibility, or use the bare string agent ID to always get latest.
