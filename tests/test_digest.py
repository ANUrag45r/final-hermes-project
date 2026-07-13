"""Tests for the project-status digest (chat + report endpoints)."""
import os
import stat
import tempfile
import pytest

from app.core.config import Settings
from app.services.hermes.control_service import HermesControlService


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


M1 = (
    "Anurag:\nI own the authentication module. The migration is complete.\n\n"
    "Sanchit:\nThe API is done. Testing is blocked until authentication is ready."
)
M2 = "Megha:\nI'll handle the documentation. The staging environment is broken."


def _seed(client):
    client.post(
        "/meetings/upload",
        json={"meeting_id": "PD1", "title": "Sprint 1", "project_id": 7, "transcript": M1},
    )
    client.post(
        "/meetings/upload",
        json={"meeting_id": "PD2", "title": "Sprint 2", "project_id": 7, "transcript": M2},
    )


def test_project_digest_via_chat(client):
    _seed(client)
    body = client.post("/chat", json={"query": "project 7 status"}).json()
    assert body["action"] == "digest"
    ans = body["answer"]
    assert "Project 7" in ans
    assert "Owners:" in ans
    assert "Anurag" in ans
    # A blocker should be surfaced.
    assert "Risks" in ans or "blocked" in ans.lower() or "broken" in ans.lower()


def test_digest_via_project_field(client):
    _seed(client)
    body = client.post(
        "/chat", json={"query": "give me the current state", "project_id": 7}
    ).json()
    assert body["action"] == "digest"
    assert "Project 7" in body["answer"]


def test_project_report_preview_endpoint(client):
    _seed(client)
    r = client.get("/reports/project/7/preview")
    assert r.status_code == 200
    data = r.json()
    assert data["scope_type"] == "project"
    assert data["stats"]["meetings"] == 2


def test_project_report_pdf_endpoint(client):
    _seed(client)
    r = client.get("/reports/project/7")
    assert r.status_code == 200
    assert r.content[:5] == b"%PDF-"


def test_plain_question_is_not_a_digest(client):
    _seed(client)
    body = client.post(
        "/chat", json={"query": "what is Anurag responsible for?", "project_id": 7}
    ).json()
    assert body["action"] == "rag"


def test_email_report_generates_pdf(client, tmp_path, monkeypatch):
    monkeypatch.setenv("REPORTS_DIR", str(tmp_path))
    _seed(client)
    # No real hermes in CI -> ok:false but the PDF is still generated on disk.
    r = client.post(
        "/reports/email",
        json={"scope": "project", "project_id": 7, "to": "boss@example.com"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "file" in body and body["file"].endswith(".pdf")


def test_email_report_missing_meeting_404(client):
    r = client.post(
        "/reports/email", json={"scope": "meeting", "meeting_id": "NOPE", "to": "a@b.com"}
    )
    assert r.status_code == 404
