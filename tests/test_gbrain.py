"""Unit tests for GBrain components in isolation."""
from tests.conftest import SAMPLE_TRANSCRIPT


def test_chunking_splits_by_speaker():
    from app.services.gbrain.chunking_service import ChunkingService

    chunks = ChunkingService().chunk(SAMPLE_TRANSCRIPT)
    assert [c["speaker"] for c in chunks] == ["Alice", "Bob", "Charlie"]
    assert "API development" in chunks[0]["content"]


def test_entity_extraction_finds_people_and_tasks():
    from app.services.gbrain.chunking_service import ChunkingService
    from app.services.gbrain.entity_extractor import EntityExtractor

    chunks = ChunkingService().chunk(SAMPLE_TRANSCRIPT)
    entities = EntityExtractor().extract(chunks)
    people = {e["name"] for e in entities if e["type"] == "person"}
    tasks = {e["name"] for e in entities if e["type"] == "task"}
    assert {"Alice", "Bob", "Charlie"} <= people
    assert "Authentication" in tasks and "Testing" in tasks


def test_graph_extraction_assigns_ownership():
    from app.services.gbrain.chunking_service import ChunkingService
    from app.services.gbrain.entity_extractor import EntityExtractor
    from app.services.gbrain.graph_extractor import GraphExtractor

    chunks = ChunkingService().chunk(SAMPLE_TRANSCRIPT)
    entities = EntityExtractor().extract(chunks)
    edges = GraphExtractor().extract(chunks, entities)
    triples = {(e["source"], e["relation"], e["target"]) for e in edges}
    assert ("Charlie", "responsible_for", "Testing") in triples


def test_vector_store_search():
    from app.services.gbrain.vector_service import LocalVectorStore

    store = LocalVectorStore(dim=256)
    store.upsert(
        "M1",
        [
            {"chunk_index": 0, "speaker": "Bob", "content": "Authentication module is pending."},
            {"chunk_index": 1, "speaker": "Charlie", "content": "I'll complete testing."},
        ],
    )
    hits = store.search("authentication", meeting_id=None, top_k=2)
    assert hits and hits[0]["speaker"] == "Bob"
