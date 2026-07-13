"""Tests for the ingestion pipeline (Stages 2-7)."""
from tests.conftest import SAMPLE_TRANSCRIPT


def test_upload_creates_memory(client):
    resp = client.post(
        "/meetings/upload",
        json={
            "meeting_id": "M001",
            "title": "Sprint Meeting",
            "transcript": SAMPLE_TRANSCRIPT,
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["meeting_id"] == "M001"
    assert body["chunks"] == 3          # Alice, Bob, Charlie
    assert body["entities"] >= 3        # at least the three people
    assert body["edges"] >= 1           # at least one relationship
    assert body["action_items"] >= 1    # Charlie -> Testing


def test_duplicate_upload_rejected(client):
    payload = {
        "meeting_id": "M002",
        "title": "Dup",
        "transcript": SAMPLE_TRANSCRIPT,
    }
    assert client.post("/meetings/upload", json=payload).status_code == 201
    assert client.post("/meetings/upload", json=payload).status_code == 409


def test_meeting_detail_has_graph(client):
    client.post(
        "/meetings/upload",
        json={"meeting_id": "M003", "title": "Graph", "transcript": SAMPLE_TRANSCRIPT},
    )
    detail = client.get("/meetings/M003").json()
    people = {e["name"] for e in detail["entities"] if e["type"] == "person"}
    assert {"Alice", "Bob", "Charlie"} <= people
    relations = {(e["source"], e["relation"], e["target"]) for e in detail["edges"]}
    assert any(r[0] == "Charlie" and r[1] == "responsible_for" for r in relations)
