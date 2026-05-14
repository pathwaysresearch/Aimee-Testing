"""
stream_events() unit tests — 13 tests.
All Anthropic API calls are mocked; no real network traffic.
"""

import json
from contextlib import contextmanager
from unittest.mock import MagicMock, patch, call
import pytest


# ---------------------------------------------------------------------------
# Helpers to build fake SDK event objects
# ---------------------------------------------------------------------------

def _make_event(type_, **kwargs):
    evt = MagicMock()
    evt.type = type_
    for k, v in kwargs.items():
        setattr(evt, k, v)
    return evt


def _text_block(text):
    block = MagicMock()
    block.type = "text"
    block.text = text
    return block


def _make_message_event(text):
    evt = _make_event("agent.message")
    evt.content = [_text_block(text)]
    return evt


def _make_tool_use_event(name="glob"):
    evt = _make_event("agent.tool_use")
    evt.name = name
    return evt


def _make_tool_result_event():
    return _make_event("agent.tool_result")


def _make_mcp_tool_use_event(name="brave_search"):
    evt = _make_event("agent.mcp_tool_use")
    evt.name = name
    return evt


def _make_mcp_tool_result_event():
    return _make_event("agent.mcp_tool_result")


def _make_error_event(message="Oops"):
    err = MagicMock()
    err.message = message
    evt = _make_event("session.error")
    evt.error = err
    return evt


# ---------------------------------------------------------------------------
# Context manager that patches run_session.client and sets up a mock stream
# ---------------------------------------------------------------------------

@contextmanager
def _mock_session(events, session_id="sess_new", config_files=None):
    """
    Patches run_session.client so that:
      - sessions.create returns a mock with .id = session_id
      - sessions.events.stream(...) yields `events` when iterated
      - sessions.events.send is a no-op
    """
    mock_client = MagicMock()
    mock_session_obj = MagicMock()
    mock_session_obj.id = session_id
    mock_client.beta.sessions.create.return_value = mock_session_obj

    # stream context manager
    mock_stream = MagicMock()
    mock_stream.__iter__ = MagicMock(return_value=iter(events))
    mock_stream.__enter__ = MagicMock(return_value=mock_stream)
    mock_stream.__exit__ = MagicMock(return_value=False)
    mock_client.beta.sessions.events.stream.return_value = mock_stream
    mock_client.beta.sessions.events.send = MagicMock()

    with patch("run_session.client", mock_client):
        yield mock_client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_new_session_created_when_no_id(config_files):
    events = [_make_message_event("hi")]
    with _mock_session(events) as mock_client:
        import run_session
        results = list(run_session.stream_events("hello"))

    mock_client.beta.sessions.create.assert_called_once()
    assert results[0] == {"type": "session_id", "value": "sess_new"}


def test_existing_session_reused(config_files):
    events = [_make_message_event("hi")]
    with _mock_session(events) as mock_client:
        import run_session
        list(run_session.stream_events("hello", session_id="sess_existing"))

    mock_client.beta.sessions.create.assert_not_called()


def test_agent_message_yields_token(config_files):
    events = [_make_message_event("Hello, world!")]
    with _mock_session(events, session_id="s1"):
        import run_session
        results = list(run_session.stream_events("hi", session_id="s1"))

    tokens = [e for e in results if e["type"] == "token"]
    assert len(tokens) == 1
    assert tokens[0]["text"] == "Hello, world!"


def test_agent_message_skips_empty_text(config_files):
    events = [_make_message_event("")]
    with _mock_session(events, session_id="s1"):
        import run_session
        results = list(run_session.stream_events("hi", session_id="s1"))

    tokens = [e for e in results if e["type"] == "token"]
    assert tokens == []


def test_tool_use_yields_start(config_files):
    events = [_make_tool_use_event("web_search")]
    with _mock_session(events, session_id="s1"):
        import run_session
        results = list(run_session.stream_events("hi", session_id="s1"))

    tool_evts = [e for e in results if e["type"] == "tool"]
    assert len(tool_evts) == 1
    assert tool_evts[0] == {"type": "tool", "name": "web_search", "done": False}


def test_tool_result_yields_done(config_files):
    events = [_make_tool_result_event()]
    with _mock_session(events, session_id="s1"):
        import run_session
        results = list(run_session.stream_events("hi", session_id="s1"))

    tool_evts = [e for e in results if e["type"] == "tool"]
    assert len(tool_evts) == 1
    assert tool_evts[0] == {"type": "tool", "name": "", "done": True}


def test_mcp_tool_use_yields_start(config_files):
    events = [_make_mcp_tool_use_event("brave_search")]
    with _mock_session(events, session_id="s1"):
        import run_session
        results = list(run_session.stream_events("hi", session_id="s1"))

    tool_evts = [e for e in results if e["type"] == "tool"]
    assert len(tool_evts) == 1
    assert tool_evts[0] == {"type": "tool", "name": "brave_search", "done": False}


def test_mcp_tool_result_yields_done(config_files):
    events = [_make_mcp_tool_result_event()]
    with _mock_session(events, session_id="s1"):
        import run_session
        results = list(run_session.stream_events("hi", session_id="s1"))

    tool_evts = [e for e in results if e["type"] == "tool"]
    assert len(tool_evts) == 1
    assert tool_evts[0] == {"type": "tool", "name": "", "done": True}


def test_session_error_yields_error_and_breaks(config_files):
    events = [_make_error_event("Bad request"), _make_message_event("never")]
    with _mock_session(events, session_id="s1"):
        import run_session
        results = list(run_session.stream_events("hi", session_id="s1"))

    error_evts = [e for e in results if e["type"] == "error"]
    assert len(error_evts) == 1
    assert error_evts[0]["text"] == "Bad request"

    # Token after the error must not appear
    tokens = [e for e in results if e["type"] == "token"]
    assert tokens == []


def test_session_terminated_breaks(config_files):
    events = [_make_event("session.status_terminated"), _make_message_event("never")]
    with _mock_session(events, session_id="s1"):
        import run_session
        results = list(run_session.stream_events("hi", session_id="s1"))

    tokens = [e for e in results if e["type"] == "token"]
    assert tokens == []


def test_session_idle_breaks(config_files):
    events = [_make_event("session.status_idle"), _make_message_event("never")]
    with _mock_session(events, session_id="s1"):
        import run_session
        results = list(run_session.stream_events("hi", session_id="s1"))

    tokens = [e for e in results if e["type"] == "token"]
    assert tokens == []


def test_session_rescheduled_continues(config_files):
    events = [
        _make_event("session.status_rescheduled"),
        _make_message_event("I continued!"),
    ]
    with _mock_session(events, session_id="s1"):
        import run_session
        results = list(run_session.stream_events("hi", session_id="s1"))

    tokens = [e for e in results if e["type"] == "token"]
    assert len(tokens) == 1
    assert tokens[0]["text"] == "I continued!"


def test_done_is_always_last(config_files):
    for events in [
        [_make_message_event("ok")],
        [_make_error_event("err")],
        [_make_event("session.status_terminated")],
    ]:
        with _mock_session(events, session_id="s1"):
            import run_session
            results = list(run_session.stream_events("hi", session_id="s1"))

        assert results[-1] == {"type": "done"}, f"Last event was {results[-1]}"


def test_load_config_reads_json(config_files):
    import run_session
    cfg = run_session.load_config()
    assert cfg["agent_id"] == "agent_test"
    assert cfg["environment_id"] == "env_test"


def test_load_resources_reads_json(config_files):
    import run_session
    resources = run_session.load_resources()
    assert isinstance(resources, list)
    assert resources[0]["file_id"] == "file_123"
