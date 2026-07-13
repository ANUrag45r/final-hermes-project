"""Pytest fixtures: isolated in-memory app with local providers."""
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Make the backend package importable and force local/offline providers.
BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))
os.environ.update(
    {
        "DATABASE_URL": "sqlite:///./test_governance_brain.db",
        "HERMES_PROVIDER": "local",
        "VECTOR_BACKEND": "local",
        "ENVIRONMENT": "test",
    }
)

SAMPLE_TRANSCRIPT = """Alice:
API development should finish this week.

Bob:
Authentication module is pending.

Charlie:
I'll complete testing.
"""


@pytest.fixture(scope="session", autouse=True)
def _clean_db():
    db_file = BACKEND.parent / "test_governance_brain.db"
    if db_file.exists():
        db_file.unlink()
    yield
    if db_file.exists():
        try:
            db_file.unlink()
        except OSError:
            pass


@pytest.fixture()
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c
