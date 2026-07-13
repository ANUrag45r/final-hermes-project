"""Direct-Composio email paths (report attachment + meeting details)."""
import pytest
from app.core.config import Settings
from app.services.integrations.composio_service import ComposioService


class _FakeTools:
    def __init__(self, calls):
        self.calls = calls

    def execute(self, slug, arguments, user_id=None, connected_account_id=None, **kwargs):
        self.calls.append((slug, arguments))
        return {"data": {"ok": True}}


class _FakeTS:
    def __init__(self):
        self.calls = []
        self.tools = _FakeTools(self.calls)


@pytest.fixture(autouse=True)
def _mock_composio_service():
    from app.main import app
    from app.core.dependencies import get_composio_service
    # Construct a mock service and inject it via dependency overrides
    svc = ComposioService(Settings(composio_api_key="ak_test_key"))
    fake_ts = _FakeTS()
    svc._toolset = fake_ts
    # Store the calls on the mock so tests can inspect them if needed
    app.dependency_overrides[get_composio_service] = lambda: svc
    yield
    app.dependency_overrides.clear()


def _svc():
    s = Settings(composio_api_key="ak_test_key")
    svc = ComposioService(s)
    svc._toolset = _FakeTS()
    return svc


def test_send_email_includes_attachment():
    svc = _svc()
    svc.send_email("gmail", "a@b.com", "Subj", "Body", attachment="/tmp/r.pdf")
    action, params = svc._toolset.calls[-1]
    assert params["attachment"] == "/tmp/r.pdf"
    assert params["recipient_email"] == "a@b.com"


def test_send_email_without_attachment_has_no_attachment_key():
    svc = _svc()
    svc.send_email("gmail", "a@b.com", "S", "B")
    _, params = svc._toolset.calls[-1]
    assert "attachment" not in params


def test_email_report_via_composio_generates_and_sends(client, tmp_path, monkeypatch):
    monkeypatch.setenv("REPORTS_DIR", str(tmp_path))
    # seed a project + meeting
    from tests.test_digest import _seed
    _seed(client)
    r = client.post(
        "/reports/email",
        json={
            "scope": "project",
            "project_id": 7,
            "to": "boss@example.com",
            "via": "composio",
            "email_provider": "gmail",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["via"] == "composio"
    assert body["file"].endswith(".pdf")


def test_send_meeting_route_404(client):
    r = client.post("/comms/send-meeting/NOPE", json={"to": "a@b.com"})
    assert r.status_code == 404
