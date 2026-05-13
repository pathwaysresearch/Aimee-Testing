"""
RUNTIME — run on every invocation.
Loads the saved agent/environment IDs and file list, starts a session with all
KB files mounted, then streams the agent's response.
"""

import json
import os
import sys

import anthropic
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


def ask_aimee(message: str) -> None:
    # Load one-time setup IDs
    with open("aimee_agent_config.json") as f:
        cfg = json.load(f)

    # Load previously uploaded file IDs (skip re-upload)
    with open("aimee_kb_files.json") as f:
        resources: list[dict] = json.load(f)

    print(f"Starting session with {len(resources)} KB files…")
    agent_ref = {"type": "agent", "id": cfg["agent_id"]}
    if cfg.get("agent_version"):
        agent_ref["version"] = cfg["agent_version"]

    session = client.beta.sessions.create(
        agent=agent_ref,
        environment_id=cfg["environment_id"],
        resources=resources,
    )
    print(f"Session: {session.id}\n")

    # Open the stream BEFORE sending the message so we don't miss early events.
    with client.beta.sessions.events.stream(session.id) as stream:
        client.beta.sessions.events.send(
            session.id,
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
                    if block.type == "text":
                        print(block.text, end="", flush=True)

            elif event.type == "agent.tool_use":
                print(f"\n[TOOL: {event.name}({getattr(event, 'input', '')})]", flush=True)

            elif event.type == "agent.tool_result":
                content = getattr(event, 'content', '')
                print(f"[RESULT: {str(content)[:200]}]", flush=True)

            elif event.type == "agent.custom_tool_use":
                # If you declared custom tools on the agent, handle them here
                # and send back a user.custom_tool_result event.
                print(f"\n[Custom tool requested: {event.name}]")

            elif event.type == "session.status_terminated":
                break

            elif event.type == "session.status_idle":
                stop_type = getattr(event, "stop_reason", {})
                if isinstance(stop_type, dict):
                    stop_type = stop_type.get("type", "")
                else:
                    stop_type = getattr(stop_type, "type", "")

                if stop_type == "requires_action":
                    # Waiting for a tool result or confirmation — keep looping.
                    continue
                # end_turn or retries_exhausted — we're done.
                break

    print()  # trailing newline after streamed output


if __name__ == "__main__":
    question = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "List all topics covered in the knowledge base."
    ask_aimee(question)
