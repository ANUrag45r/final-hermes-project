"""Tests for the report generator (preview JSON + PDF)."""
SAMPLE = """Prerit:
I will own the API integration and have it ready by Thursday.

Anurag:
Authentication is still pending. The migration is blocked.

Shanank:
Testing is complete and the deployment passed."""


def _seed(client, mid="R001"):
    client.post(
        "/meetings/upload",
        json={"meeting_id": mid, "title": "Status Sync", "transcript": SAMPLE},
    )


def test_meeting_report_preview(client):
    _seed(client, "R001")
    r = client.get("/reports/meeting/R001/preview")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["scope_type"] == "meeting"
    assert body["stats"]["people"] >= 3
    assert body["merits"] and body["demerits"]
    # A blocker cue should surface as a demerit.
    assert any("Risk" in d["text"] or "unassigned" in d["text"] for d in body["demerits"])


def test_meeting_report_pdf(client):
    _seed(client, "R002")
    r = client.get("/reports/meeting/R002")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:5] == b"%PDF-"
    assert "attachment" in r.headers.get("content-disposition", "")


def test_weekly_report_pdf(client):
    _seed(client, "R003")
    r = client.get("/reports/weekly")
    assert r.status_code == 200
    assert r.content[:5] == b"%PDF-"


def test_missing_meeting_report_404(client):
    assert client.get("/reports/meeting/NOPE/preview").status_code == 404


def test_run_skill_success(client, monkeypatch):
    _seed(client, "R004")
    
    def mock_run_skill_on_transcript(self, skill_name, transcript, timeout=300.0):
        return {
            "ok": True,
            "output": "## MOCK REPORT\n\nThis is a mock technical spec generated for the meeting.\n- Action Item 1\n- Action Item 2",
            "skill": skill_name
        }
        
    from app.services.hermes.gstack_service import GStackService
    monkeypatch.setattr(GStackService, "run_skill_on_transcript", mock_run_skill_on_transcript)
    
    response = client.post("/reports/run-skill", json={"skill_name": "spec", "meeting_id": "R004"})
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert "MOCK REPORT" in body["markdown"]
    assert "pdf_url" in body
    
    # Verify download endpoint
    download_url = body["pdf_url"]
    download_resp = client.get(download_url)
    assert download_resp.status_code == 200
    assert download_resp.headers["content-type"] == "application/pdf"
    assert download_resp.content[:5] == b"%PDF-"


def test_run_skill_meeting_404(client):
    response = client.post("/reports/run-skill", json={"skill_name": "spec", "meeting_id": "NOPE"})
    assert response.status_code == 404


def test_gstack_report_endpoints(client, tmp_path, monkeypatch):
    _seed(client, "R005")
    
    dummy_pdf = tmp_path / "dummy.pdf"
    dummy_pdf.write_bytes(b"%PDF-1.4 dummy gstack pdf")
    
    def mock_run_skill(self, skill_id, scope_id, title, content):
        return {"ok": True, "produced_file": str(dummy_pdf)}
        
    from app.services.hermes.gstack_service import GStackService
    from app.core.config import get_settings
    monkeypatch.setattr(GStackService, "run_skill", mock_run_skill)
    monkeypatch.setattr(get_settings(), "gstack_dir", str(tmp_path))
    
    # 1. Test meeting gstack pdf
    res = client.get("/reports/meeting/R005/gstack")
    assert res.status_code == 200
    assert res.content == b"%PDF-1.4 dummy gstack pdf"
    
    # 2. Test weekly gstack pdf
    res = client.get("/reports/weekly/gstack?date=2026-06-24")
    assert res.status_code == 200
    assert res.content == b"%PDF-1.4 dummy gstack pdf"
    
    # 3. Test project gstack pdf
    res = client.get("/reports/project/0/gstack")
    assert res.status_code == 200
    assert res.content == b"%PDF-1.4 dummy gstack pdf"
    
    # 4. Test email report with gstack flag
    from app.services.integrations.composio_service import ComposioService
    from pathlib import Path
    def mock_send_email(self, provider, to, subject, body, attachment=None):
        assert attachment is not None
        content = Path(attachment).read_bytes()
        assert content == b"%PDF-1.4 dummy gstack pdf"
        return {"ok": True, "data": "sent"}
        
    monkeypatch.setattr(ComposioService, "send_email", mock_send_email)
    
    email_req = {
        "scope": "meeting",
        "meeting_id": "R005",
        "to": "test@example.com",
        "via": "composio",
        "email_provider": "gmail",
        "gstack": True
    }
    res = client.post("/reports/email", json=email_req)
    assert res.status_code == 200
    assert res.json()["ok"] is True


