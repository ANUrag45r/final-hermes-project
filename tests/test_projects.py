"""Tests for grouping meetings into projects and scoping chat to a project."""

P1_A = "Anurag:\nI own the authentication module for the billing system."
P1_B = "Anurag:\nThe billing migration is complete."
P2_A = "Megha:\nI own the recommendation engine for the analytics project."


def _upload(client, mid, transcript, project_id):
    return client.post(
        "/meetings/upload",
        json={
            "meeting_id": mid,
            "title": mid,
            "transcript": transcript,
            "project_id": project_id,
        },
    )


def _seed_projects(client):
    _upload(client, "P1M1", P1_A, 1)
    _upload(client, "P1M2", P1_B, 1)
    _upload(client, "P2M1", P2_A, 2)


def test_projects_listed(client):
    _seed_projects(client)
    projects = {p["project_id"]: p for p in client.get("/meetings/projects").json()}
    assert projects[1]["meetings"] == 2
    assert projects[2]["meetings"] == 1


def test_chat_scoped_to_project_via_field(client):
    _seed_projects(client)
    # Scope to project 1: only project-1 meetings should appear as evidence.
    body = client.post(
        "/chat", json={"query": "what is owned here?", "project_id": 1}
    ).json()
    hit_meetings = {h["meeting_id"] for h in body["context"]["vector_hits"]}
    assert hit_meetings and hit_meetings <= {"P1M1", "P1M2"}
    assert "P2M1" not in hit_meetings


def test_chat_scoped_to_project_via_text(client):
    _seed_projects(client)
    # "project 2" parsed from the text restricts to project 2.
    body = client.post(
        "/chat", json={"query": "in project 2 who owns what?"}
    ).json()
    hit_meetings = {h["meeting_id"] for h in body["context"]["vector_hits"]}
    assert hit_meetings <= {"P2M1"}
    facts = {(f["source"], f["target"]) for f in body["context"]["graph_facts"]}
    # No project-1 owner (Anurag) should leak into a project-2 scoped answer.
    assert all(src != "Anurag" for src, _ in facts)
