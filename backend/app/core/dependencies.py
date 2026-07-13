"""
Composition root.

All object graphs are assembled here and handed to routes via FastAPI's
dependency system. Routes therefore depend on *abstractions* constructed here,
never on concrete classes — keeping the wiring in one auditable place.

The vector store and Hermes service are process-singletons (the local vector
index must persist across requests); repositories and request-scoped services
are built per request around the active DB session.
"""
from functools import lru_cache

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.graph_repository import GraphRepository
from app.services.integrations.composio_service import ComposioService
from app.services.hermes.control_service import HermesControlService
from app.repositories.meeting_repository import MeetingRepository
from app.repositories.report_repository import ReportRepository
from app.services.chat.chat_service import ChatService
from app.services.gbrain.chunking_service import ChunkingService
from app.services.gbrain.entity_extractor import EntityExtractor
from app.services.gbrain.gbrain_service import GBrainService
from app.services.gbrain.graph_extractor import GraphExtractor
from app.services.gbrain.vector_service import build_vector_store
from app.services.hermes.hermes_service import HermesService, build_hermes_service
from app.services.ingestion.meeting_ingestion import MeetingIngestionService
from app.services.integrations.mail_service import MailService
from app.services.reporting.report_builder import ReportBuilder
from app.services.reporting.report_service import ReportService


# --- process singletons -----------------------------------------------------
@lru_cache
def get_vector_store():
    """Single shared vector index for the process lifetime."""
    return build_vector_store(get_settings())


@lru_cache
def get_hermes_service() -> HermesService:
    return build_hermes_service(get_settings())


@lru_cache
def get_mail_service() -> MailService:
    return MailService(get_settings())


# --- request-scoped wiring --------------------------------------------------
def get_gbrain(db: Session = Depends(get_db)) -> GBrainService:
    return GBrainService(
        chunker=ChunkingService(),
        entity_extractor=EntityExtractor(),
        graph_extractor=GraphExtractor(),
        vector_store=get_vector_store(),
        chunk_repo=ChunkRepository(db),
        graph_repo=GraphRepository(db),
    )


def get_ingestion_service(
    db: Session = Depends(get_db),
    gbrain: GBrainService = Depends(get_gbrain),
) -> MeetingIngestionService:
    return MeetingIngestionService(
        gbrain=gbrain,
        meeting_repo=MeetingRepository(db),
        chunk_repo=ChunkRepository(db),
    )


def get_gstack_service() -> "GStackService":
    """gstack skills integration (lists skills, runs them on meetings)."""
    from app.services.hermes.gstack_service import GStackService

    settings = get_settings()
    return GStackService(settings, HermesControlService(settings))


def get_chat_service(
    db: Session = Depends(get_db),
    gbrain: GBrainService = Depends(get_gbrain),
    hermes: HermesService = Depends(get_hermes_service),
    mail: MailService = Depends(get_mail_service),
    gstack: "GStackService" = Depends(get_gstack_service),
) -> ChatService:
    reports = ReportService(
        builder=ReportBuilder(ReportRepository(db)),
        hermes=hermes,
        gstack=gstack,
    )
    return ChatService(
        gbrain=gbrain,
        hermes=hermes,
        mail=mail,
        meeting_repo=MeetingRepository(db),
        reports=reports,
    )


def get_report_service(
    db: Session = Depends(get_db),
    hermes: HermesService = Depends(get_hermes_service),
    gstack: "GStackService" = Depends(get_gstack_service),
) -> ReportService:
    return ReportService(
        builder=ReportBuilder(ReportRepository(db)),
        hermes=hermes,
        gstack=gstack,
    )


@lru_cache
def get_composio_service() -> ComposioService:
    """Cached Composio service (holds one lazily-built SDK toolset)."""
    return ComposioService(get_settings())


def get_hermes_control_service() -> HermesControlService:
    """Read-only Hermes CLI control panel service."""
    return HermesControlService(get_settings())


# Re-export for convenience
__all__ = [
    "Settings",
    "get_settings",
    "get_vector_store",
    "get_hermes_service",
    "get_gbrain",
    "get_ingestion_service",
    "get_chat_service",
    "get_report_service",
    "get_composio_service",
    "get_hermes_control_service",
]
