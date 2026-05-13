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
python setup_agent.py

# 2. Upload KB markdown files (once per KB change)
python upload_kb.py

# 3. Start a session and ask a question
python run_session.py "What does chapter 2 cover?"
```

`setup_agent.py` writes `aimee_agent_config.json` (agent ID + version + environment ID).  
`upload_kb.py` writes `aimee_kb_files.json` (list of `{type, file_id, mount_path}` dicts).  
`run_session.py` reads both JSON files at runtime — no re-upload, no re-creation.

## Architecture

### Managed agents constraint
`model`, `system`, and `tools` belong on the **agent object**, never on the session. Sessions are thin — they only accept an `agent` pointer and optional `resources`. This is why setup and runtime are split.

### File mounting
KB files are uploaded to the Anthropic Files API (`client.beta.files.upload`) and attached to each session as resources with explicit `mount_path` values under `/workspace/aimee/`. The agent reads them using its built-in `read`/`glob` tools.

### Stream-first pattern
In `run_session.py`, the SSE stream is opened **before** `events.send` is called. This prevents missing early events (the stream doesn't replay history — it only delivers events emitted after it opens).

### Session idle-break logic
`session.status_idle` fires transiently (e.g., while waiting on a tool confirmation). The loop only breaks when `stop_reason.type` is `end_turn` or `retries_exhausted`; it continues when `requires_action`.

## Key files produced at runtime

| File | Contents |
|---|---|
| `aimee_agent_config.json` | `agent_id`, `agent_version`, `environment_id` |
| `aimee_kb_files.json` | Array of `{type, file_id, mount_path}` for each uploaded `.md` file |

## Changing the knowledge base folder

`upload_kb.py` defaults `KB_FOLDER` to `Path("./")` (current directory). Change this constant or pass a different `Path` to `upload_kb()` to point at a different folder.

## Updating the agent

To change the system prompt or tools, edit `setup_agent.py` and call `client.beta.agents.update(agent_id, ...)` rather than creating a new agent. Each update bumps the version; pin the version in `aimee_agent_config.json` for reproducibility, or use the bare string agent ID to always get latest.
