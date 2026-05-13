"""
Flask route tests — 7 tests covering /, /chat validation, SSE format, and
session_id pass-through. The Anthropic client is mocked so no real API calls
are made.
"""

import json
from unittest.mock import patch, MagicMock


def test_index_returns_html(client):
    res = client.get("/")
    assert res.status_code == 200
    assert "text/html" in res.content_type
    assert b"Aimee" in res.data


def test_chat_empty_message_400(client):
    res = client.post(
        "/chat",
        data=json.dumps({"message": ""}),
        content_type="application/json",
    )
    assert res.status_code == 400


def test_chat_missing_message_400(client):
    res = client.post(
        "/chat",
        data=json.dumps({}),
        content_type="application/json",
    )
    assert res.status_code == 400


def _mock_stream_events(message, session_id=None):
    yield {"type": "session_id", "value": "sess_abc"}
    yield {"type": "token", "text": "Hello!"}
    yield {"type": "done"}


def test_chat_returns_event_stream(client):
    with patch("api.index.stream_events", side_effect=_mock_stream_events):
        res = client.post(
            "/chat",
            data=json.dumps({"message": "Hi"}),
            content_type="application/json",
        )
    assert res.status_code == 200
    assert "text/event-stream" in res.content_type


def test_chat_sse_lines_format(client):
    with patch("api.index.stream_events", side_effect=_mock_stream_events):
        res = client.post(
            "/chat",
            data=json.dumps({"message": "Hi"}),
            content_type="application/json",
        )
    raw = res.data.decode()
    # Every non-empty line must start with "data: " and contain valid JSON
    for line in raw.split("\n"):
        line = line.strip()
        if not line:
            continue
        assert line.startswith("data: "), f"Bad SSE line: {line!r}"
        json.loads(line[6:])  # must parse as JSON


def test_chat_passes_session_id(client):
    calls = []

    def capturing_stream(message, session_id=None):
        calls.append(session_id)
        yield {"type": "done"}

    with patch("api.index.stream_events", side_effect=capturing_stream):
        client.post(
            "/chat",
            data=json.dumps({"message": "Hi", "session_id": "sess_xyz"}),
            content_type="application/json",
        )

    assert calls == ["sess_xyz"]


def test_chat_none_session_id_when_absent(client):
    calls = []

    def capturing_stream(message, session_id=None):
        calls.append(session_id)
        yield {"type": "done"}

    with patch("api.index.stream_events", side_effect=capturing_stream):
        client.post(
            "/chat",
            data=json.dumps({"message": "Hi"}),
            content_type="application/json",
        )

    assert calls == [None]
