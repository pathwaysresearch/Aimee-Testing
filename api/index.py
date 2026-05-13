import json
import sys
from pathlib import Path
from flask import Flask, Response, render_template, request, stream_with_context

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from run_session import stream_events  # noqa: E402

app = Flask(
    __name__,
    template_folder=str(ROOT / "templates"),
    static_folder=str(ROOT / "static"),
)


def sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


def stream_response(message: str, session_id: str | None):
    for evt in stream_events(message, session_id):
        yield sse(evt)


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
