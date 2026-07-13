"""Tests for the Contact (Composio) integration.

These never hit Composio's network: the service's SDK toolset is replaced with
a fake that records calls, so we verify slug/param routing and graceful
degradation when unconfigured.
"""
import pytest

from app.core.config import Settings
from app.services.integrations.composio_service import (
    ComposioError,
    ComposioService,
)


class _FakeConnectedAccounts:
    def list(self, timeout=None):
        class A:
            id = "conn_1"
            status = "ACTIVE"
            user_id = "default"
            class T:
                slug = "gmail"
            toolkit = T()
        class R:
            items = [A()]
        return R()


class _FakeTools:
    def __init__(self, calls):
        self.calls = calls

    def execute(self, slug, arguments, user_id=None, connected_account_id=None, **kwargs):
        self.calls.append((slug, arguments, user_id))
        return {"successful": True, "data": {"messages": [{"subject": "hi"}]}}


class _FakeClientTools:
    def list(self, toolkit_slug=None, timeout=None):
        class S:
            slug = "GMAIL_FETCH_EMAILS"
            name = "Fetch emails from Gmail"
            description = "Fetch emails from Gmail"
        class R:
            items = [S()]
        return R()


class _FakeClient:
    def __init__(self):
        self.tools = _FakeClientTools()


class _FakeToolSet:
    def __init__(self):
        self.calls = []
        self.connected_accounts = _FakeConnectedAccounts()
        self.tools = _FakeTools(self.calls)
        self.client = _FakeClient()


def _svc(**over) -> ComposioService:
    settings = Settings(composio_api_key="ak_test_key", composio_entity_id="default", **over)
    svc = ComposioService(settings)
    svc._toolset = _FakeToolSet()  # inject fake, bypass real SDK
    return svc


def test_unconfigured_is_graceful():
    svc = ComposioService(Settings(composio_api_key=""))
    assert svc.enabled is False
    with pytest.raises(ComposioError):
        svc.connections()


def test_connections_listed():
    svc = _svc()
    conns = svc.connections()
    assert conns[0]["app"] == "gmail"
    assert conns[0]["status"] == "ACTIVE"


def test_fetch_emails_uses_configured_slug():
    svc = _svc()
    svc.fetch_emails("gmail", limit=5)
    action, params, entity = svc._toolset.calls[-1]
    assert action == "GMAIL_FETCH_EMAILS"
    assert params == {"max_results": 5}
    assert entity == "default"


def test_send_email_maps_fields_per_provider():
    svc = _svc()
    svc.send_email("gmail", "a@b.com", "Hi", "Body")
    action, params, _ = svc._toolset.calls[-1]
    assert action == "GMAIL_SEND_EMAIL"
    assert params["recipient_email"] == "a@b.com"

    svc.send_email("outlook", "c@d.com", "Yo", "Text")
    action, params, _ = svc._toolset.calls[-1]
    assert action == "OUTLOOK_OUTLOOK_SEND_EMAIL"
    assert params["to_email"] == "c@d.com"


def test_execute_extracts_data():
    svc = _svc()
    out = svc.execute("GMAIL_FETCH_EMAILS", {"max_results": 1})
    assert out["data"] == {"messages": [{"subject": "hi"}]}


def test_slug_override_from_settings():
    svc = _svc(composio_gmail_fetch="GMAIL_CUSTOM_FETCH")
    svc.fetch_emails("gmail")
    assert svc._toolset.calls[-1][0] == "GMAIL_CUSTOM_FETCH"


def test_status_route_unconfigured(client, monkeypatch):
    # The app's composio service is unconfigured by default in tests.
    from app.main import app
    from app.core.dependencies import get_composio_service
    app.dependency_overrides[get_composio_service] = lambda: ComposioService(Settings(composio_api_key=""))
    try:
        r = client.get("/comms/status")
        assert r.status_code == 200
        body = r.json()
        assert body["enabled"] is False
        assert "COMPOSIO_API_KEY" in (body["error"] or "")
    finally:
        app.dependency_overrides.clear()

