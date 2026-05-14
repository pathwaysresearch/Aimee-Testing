"""
Shared session core — importable by api/index.py (SSE web) and usable as CLI.

Exports:
  stream_events(message, session_id=None) -> Iterator[dict]
    Yields transport-neutral event dicts:
      {"type": "session_id", "value": str}
      {"type": "token",      "text": str}
      {"type": "tool",       "name": str, "done": bool}
      {"type": "error",      "text": str}
      {"type": "done"}

CLI:
  python run_session.py "Your question here"
"""

import json
import os
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).parent
client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


def load_config() -> dict:
    with open(ROOT / "aimee_agent_config.json") as f:
        return json.load(f)


def load_resources() -> list:
    with open(ROOT / "aimee_kb_files.json") as f:
        return json.load(f)


def stream_events(message: str, session_id: str | None = None):
    cfg = load_config()
    resources = load_resources()

    if not session_id:
        agent_ref = {"type": "agent", "id": cfg["agent_id"]}
        if cfg.get("agent_version"):
            agent_ref["version"] = cfg["agent_version"]

        session = client.beta.sessions.create(
            agent=agent_ref,
            environment_id=cfg["environment_id"],
            resources=resources,
        )
        session_id = session.id
        yield {"type": "session_id", "value": session_id}

    with client.beta.sessions.events.stream(session_id=session_id) as stream:
        client.beta.sessions.events.send(
            session_id=session_id,
            events=[
                {
                    "type": "user.message",
                    "content": [{"type": "text", "text": message}],
                }
            ],
        )

        for event in stream:
            if event.type == "agent.message":
                for block in event.content:
                    if block.type == "text" and block.text:
                        yield {"type": "token", "text": block.text}

            elif event.type == "agent.tool_use":
                yield {"type": "tool", "name": event.name, "done": False}

            elif event.type == "agent.tool_result":
                yield {"type": "tool", "name": "", "done": True}

            elif event.type == "agent.mcp_tool_use":
                yield {"type": "tool", "name": event.name, "done": False}

            elif event.type == "agent.mcp_tool_result":
                yield {"type": "tool", "name": "", "done": True}

            elif event.type == "session.error":
                msg = getattr(getattr(event, "error", None), "message", "Unknown error")
                yield {"type": "error", "text": msg}
                break

            elif event.type in ("session.status_terminated", "session.status_idle"):
                break

            # session.status_rescheduled, session.status_running → fall through

    yield {"type": "done"}


def _cli_render(evt: dict) -> None:
    t = evt["type"]
    if t == "token":
        print(evt["text"], end="", flush=True)
    elif t == "tool" and not evt["done"]:
        print(f"\n[Using {evt['name']}…]", flush=True)
    elif t == "error":
        print(f"\n[Error: {evt['text']}]")
    elif t == "done":
        print()


if __name__ == "__main__":
    import sys

    question = (
        " ".join(sys.argv[1:])
        if len(sys.argv) > 1
        else "List all topics covered in the knowledge base."
    )
    for evt in stream_events(question):
        _cli_render(evt)
