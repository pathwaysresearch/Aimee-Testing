import json
import os
import sys
from pathlib import Path
from flask import Flask, Response, render_template, request, stream_with_context
import anthropic
from dotenv import load_dotenv

load_dotenv()

# Allow imports and template/static resolution from the project root
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

app = Flask(
    __name__,
    template_folder=str(ROOT / "templates"),
    static_folder=str(ROOT / "static"),
)

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

def load_config():
    with open(ROOT / "aimee_agent_config.json") as f:
        return json.load(f)

def load_resources():
    with open(ROOT / "aimee_kb_files.json") as f:
        return json.load(f)


def sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


def stream_response(message: str, session_id: str | None):
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
        yield sse({"type": "session_id", "value": session_id})

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
                        yield sse({"type": "token", "text": block.text})

            elif event.type == "agent.tool_use":
                yield sse({"type": "tool", "name": event.name})

            elif event.type == "session.status_terminated":
                break

            elif event.type == "session.status_idle":
                stop_type = getattr(event, "stop_reason", {})
                if isinstance(stop_type, dict):
                    stop_type = stop_type.get("type", "")
                else:
                    stop_type = getattr(stop_type, "type", "")

                if stop_type == "requires_action":
                    continue
                break

    yield sse({"type": "done"})


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/chat", methods=["POST"])
def chat():
    body = request.get_json()
    message = body.get("message", "").strip()
    session_id = body.get("session_id") or None

    if not message:
        return {"error": "empty message"}, 400

    return Response(
        stream_with_context(stream_response(message, session_id)),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


if __name__ == "__main__":
    app.run(debug=True, port=5000)
