import os
import sys
import json
import pytest

# Ensure repo root is on sys.path so api.index and run_session can be imported
ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, ROOT)


@pytest.fixture
def app():
    from api.index import app as flask_app
    flask_app.config["TESTING"] = True
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def config_files(tmp_path, monkeypatch):
    """
    Write minimal aimee_agent_config.json and aimee_kb_files.json into a
    temp directory and patch run_session.ROOT so load_config / load_resources
    read from there instead of the real files.
    """
    cfg = {"agent_id": "agent_test", "agent_version": 1, "environment_id": "env_test"}
    resources = [{"type": "file", "file_id": "file_123", "mount_path": "/workspace/test.md"}]

    (tmp_path / "aimee_agent_config.json").write_text(json.dumps(cfg))
    (tmp_path / "aimee_kb_files.json").write_text(json.dumps(resources))

    import run_session
    monkeypatch.setattr(run_session, "ROOT", tmp_path)

    return {"cfg": cfg, "resources": resources, "tmp_path": tmp_path}
