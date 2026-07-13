"""Tests for the query flow (Stages 8-9)."""
from tests.conftest import SAMPLE_TRANSCRIPT


def _seed(client, meeting_id="C001"):
    client.post(
        "/meetings/upload",
        json={
            "meeting_id": meeting_id,
            "title": "Sprint",
            "transcript": SAMPLE_TRANSCRIPT,
        },
    )


def test_chat_answers_from_graph(client):
    _seed(client, "C001")
    resp = client.post("/chat", json={"query": "What task was assigned to Bob?"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "Authentication" in body["answer"]
    assert body["provider"] == "local"
    # Evidence is returned, not just the answer.
    assert body["context"]["graph_facts"] or body["context"]["vector_hits"]


def test_chat_vector_recall(client):
    _seed(client, "C002")
    resp = client.post(
        "/chat",
        json={"query": "who handles testing?", "meeting_id": "C002"},
    )
    body = resp.json()
    assert body["context"]["vector_hits"], "expected semantic hits"
    assert "Charlie" in body["answer"] or "testing" in body["answer"].lower()


def test_chat_empty_memory_is_graceful(client):
    resp = client.post(
        "/chat", json={"query": "anything?", "meeting_id": "DOES_NOT_EXIST"}
    )
    assert resp.status_code == 200
    assert isinstance(resp.json()["answer"], str)
