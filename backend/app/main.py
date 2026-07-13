"""FastAPI application entrypoint."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    agent_routes,
    chat_routes,
    comms_routes,
    dashboard_routes,
    meeting_routes,
    report_routes,
)
from app.core.config import get_settings
from app.core.database import SessionLocal, init_db
from app.core.dependencies import get_vector_store
from app.repositories.chunk_repository import ChunkRepository
from app.utils.logger import get_logger

logger = get_logger("main")
settings = get_settings()


def _rehydrate_vectors() -> None:
    """Rebuild the in-process vector index from persisted chunks on startup.

    The structured store (SQLite/Postgres) already persists across restarts;
    the local vector index lives in memory, so we repopulate it here. With an
    external vector DB (Qdrant) this is a no-op because those vectors persist.
    """
    if settings.vector_backend != "local":
        return
    store = get_vector_store()
    db = SessionLocal()
    try:
        chunks = ChunkRepository(db).all_chunks()
        by_meeting: dict[str, list[dict]] = {}
        for c in chunks:
            by_meeting.setdefault(c.meeting_id, []).append(
                {"chunk_index": c.chunk_index, "speaker": c.speaker, "content": c.content}
            )
        for meeting_id, items in by_meeting.items():
            store.upsert(meeting_id, items)
        if chunks:
            logger.info("Rehydrated vectors for %d meeting(s)", len(by_meeting))
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting %s (env=%s)", settings.app_name, settings.environment)
    from app.core.config import _ENV_FILE

    logger.info("Config .env: %s (exists=%s)", _ENV_FILE, _ENV_FILE.exists())
    init_db()
    _rehydrate_vectors()
    from app.services.ingestion.downloads_watcher import start_downloads_watcher
    start_downloads_watcher()
    logger.info(
        "Memory ready | hermes=%s | vectors=%s | mail=%s",
        settings.hermes_provider,
        settings.vector_backend,
        "on" if settings.graph_enabled else "off",
    )
    yield
    from app.services.ingestion.downloads_watcher import stop_downloads_watcher
    stop_downloads_watcher()
    logger.info("Shutting down")


app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    # Accept any localhost / 127.0.0.1 port in dev (vite dev, preview, static
    # servers, etc.) so the browser can call the API directly without a proxy.
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(meeting_routes.router, prefix=settings.api_prefix)
app.include_router(chat_routes.router, prefix=settings.api_prefix)
app.include_router(dashboard_routes.router, prefix=settings.api_prefix)
app.include_router(report_routes.router, prefix=settings.api_prefix)
app.include_router(comms_routes.router, prefix=settings.api_prefix)
app.include_router(agent_routes.router, prefix=settings.api_prefix)


@app.get("/health", tags=["system"])
def health():
    from app.core.config import _ENV_FILE

    return {
        "status": "ok",
        "app": settings.app_name,
        "hermes_provider": settings.hermes_provider,
        "hermes_base_url": settings.hermes_base_url,
        "hermes_agentic": settings.hermes_agentic,
        "vector_backend": settings.vector_backend,
        "env_file": str(_ENV_FILE),
        "env_file_exists": _ENV_FILE.exists(),
    }
