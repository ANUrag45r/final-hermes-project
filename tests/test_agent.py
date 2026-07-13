"""Tests for the Hermes Agent control panel (read-only CLI monitoring)."""
import os
import stat
import tempfile

import pytest

from app.core.config import Settings
from app.services.hermes.control_service import (
    HermesControlError,
    HermesControlService,
)


def _fake_hermes() -> str:
    """Create a fake hermes executable that echoes the subcommand."""
    import sys
    if sys.platform.startswith("win"):
        fd, path = tempfile.mkstemp(suffix=".bat")
        with os.fdopen(fd, "w") as f:
            f.write("@echo off\necho FAKE hermes %*\n")
        return path
    else:
        fd, path = tempfile.mkstemp(suffix=".sh")
        with os.fdopen(fd, "w") as f:
            f.write("#!/usr/bin/env bash\necho \"FAKE hermes $*\"\n")
        os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC | stat.S_IXGRP)
        return path


@pytest.fixture(autouse=True)
def _mock_hermes_control():
    from app.main import app
    from app.core.dependencies import get_hermes_control_service
    fake_exe = _fake_hermes()
    fake_svc = HermesControlService(Settings(hermes_cli_path=fake_exe))
    app.dependency_overrides[get_hermes_control_service] = lambda: fake_svc
    yield
    app.dependency_overrides.clear()



def test_actions_allowlist():
    svc = HermesControlService(Settings())
    assert set(svc.actions) >= {"status", "sessions", "profiles", "insights", "logs"}


def test_unknown_action_rejected():
    svc = HermesControlService(Settings(hermes_cli_path=_fake_hermes()))
    with pytest.raises(HermesControlError):
        svc.run("rm_rf_everything")  # not in allowlist


def test_run_status_executes_cli():
    svc = HermesControlService(Settings(hermes_cli_path=_fake_hermes()))
    res = svc.run("status")
    assert res["ok"] is True
    assert "status" in res["output"]
    assert res["command"] == "hermes status"


def test_missing_binary_is_friendly():
    svc = HermesControlService(Settings(hermes_cli_path="/no/such/hermes/binary"))
    with pytest.raises(HermesControlError) as ei:
        svc.run("status")
    assert "not found" in str(ei.value).lower()


def test_agent_status_route(client):
    r = client.get("/agent/status")
    assert r.status_code == 200
    body = r.json()
    assert "actions" in body and "status" in body["actions"]


def test_chat_runs_cli_query():
    svc = HermesControlService(Settings(hermes_cli_path=_fake_hermes()))
    res = svc.chat("give my last 3 mails")
    assert res["ok"] is True
    assert "chat -q" in res["output"]  # fake echoes the args
    assert res["command"] == "hermes chat -q …"


def test_chat_rejects_empty():
    svc = HermesControlService(Settings(hermes_cli_path=_fake_hermes()))
    with pytest.raises(HermesControlError):
        svc.chat("   ")


def test_agent_chat_route(client):
    # No real hermes in CI -> friendly 400, not a 500 crash.
    r = client.post("/agent/chat", json={"message": "hello"})
    assert r.status_code in (200, 400)


def test_save_to_gbrain_builds_query(tmp_path):
    svc = HermesControlService(
        Settings(hermes_cli_path=_fake_hermes(), gbrain_feed_dir=str(tmp_path))
    )
    res = svc.save_to_gbrain("M99", "Sprint sync", "Riya:\nI own the API.")
    assert res["ok"] is True
    assert "put_page meeting-M99" in res["command"]
    assert (tmp_path / "meeting-M99.txt").exists()
    assert "Sprint sync" in (tmp_path / "meeting-M99.txt").read_text()


def test_save_empty_transcript_rejected(tmp_path):
    svc = HermesControlService(
        Settings(hermes_cli_path=_fake_hermes(), gbrain_feed_dir=str(tmp_path))
    )
    with pytest.raises(HermesControlError):
        svc.save_to_gbrain("M1", "t", "   ")


def test_save_meeting_route_404_for_missing(client):
    r = client.post("/agent/save-meeting/NOPE_404")
    assert r.status_code == 404


def test_email_file_builds_query():
    svc = HermesControlService(Settings(hermes_cli_path=_fake_hermes()))
    res = svc.email_file("a@b.com", "Subj", "Body", "/tmp/report.pdf")
    assert res["ok"] is True
    assert res["to"] == "a@b.com"
    assert "email report to a@b.com" in res["command"]


def test_email_file_requires_recipient():
    svc = HermesControlService(Settings(hermes_cli_path=_fake_hermes()))
    with pytest.raises(HermesControlError):
        svc.email_file("", "s", "b", "/tmp/x.pdf")
