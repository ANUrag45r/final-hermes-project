"""Tests for delete, edit, persistence and mail-intent routing."""
from tests.conftest import SAMPLE_TRANSCRIPT


def _seed(client, mid):
    return client.post(
        "/meetings/upload",
        json={"meeting_id": mid, "title": "Sprint", "transcript": SAMPLE_TRANSCRIPT},
    )


def test_delete_meeting(client):
    _seed(client, "D001")
    assert client.get("/meetings/D001").status_code == 200
    assert client.delete("/meetings/D001").status_code == 204
    assert client.get("/meetings/D001").status_code == 404
    # Chat scoped to the deleted meeting finds nothing.
    body = client.post("/chat", json={"query": "Bob", "meeting_id": "D001"}).json()
    assert not body["context"]["graph_facts"]


def test_delete_missing_404(client):
    assert client.delete("/meetings/NOPE").status_code == 404


def test_edit_title_only(client):
    _seed(client, "E001")
    r = client.patch("/meetings/E001", json={"title": "Renamed Sprint"})
    assert r.status_code == 200
    assert client.get("/meetings/E001").json()["title"] == "Renamed Sprint"


def test_edit_append_transcript_rebuilds_memory(client):
    _seed(client, "E002")
    before = client.get("/meetings/E002").json()
    n_chunks_before = len(before["chunks"])
    r = client.patch(
        "/meetings/E002",
        json={"append_transcript": "Dana:\nI'll own the deployment."},
    )
    assert r.status_code == 200
    after = client.get("/meetings/E002").json()
    assert len(after["chunks"]) == n_chunks_before + 1
    people = {e["name"] for e in after["entities"] if e["type"] == "person"}
    assert "Dana" in people
    # New ownership is queryable.
    ans = client.post("/chat", json={"query": "who owns deployment?"}).json()
    assert "Dana" in ans["answer"] or "deployment" in ans["answer"].lower()


def test_mail_intent_when_not_configured(client):
    # No Graph creds in the test env, so mail intents return a help message.
    r = client.post("/chat", json={"query": "fetch my last 3 mails"})
    assert r.status_code == 200
    body = r.json()
    assert body["action"] == "mail_help"
    assert "env" in body["answer"].lower() or "connect" in body["answer"].lower()


def test_non_mail_query_still_uses_rag(client):
    _seed(client, "E003")
    body = client.post("/chat", json={"query": "What task was assigned to Bob?"}).json()
    assert body["action"] == "rag"
    assert "Authentication" in body["answer"]


def test_auto_ingest_settings(client):
    r = client.get("/meetings/auto-ingest")
    assert r.status_code == 200
    assert r.json() == {"enabled": False}

    r = client.post("/meetings/auto-ingest", json={"enabled": True})
    assert r.status_code == 200
    assert r.json() == {"enabled": True}

    r = client.get("/meetings/auto-ingest")
    assert r.status_code == 200
    assert r.json() == {"enabled": True}
