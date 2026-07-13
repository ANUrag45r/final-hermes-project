"""SQLAlchemy engine / session wiring (the structured-storage boundary)."""
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

# check_same_thread is only needed for SQLite; harmless to compute conditionally.
_connect_args = (
    {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)

engine = create_engine(
    settings.database_url,
    connect_args=_connect_args,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a scoped session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create tables, then apply lightweight in-place migrations.

    create_all() never ALTERs existing tables, so databases created before a
    column was added would be missing it. We additively add known-missing
    columns (safe, non-destructive) so existing data keeps working.
    """
    from app import models  # noqa: F401  (side-effect import)

    Base.metadata.create_all(bind=engine)
    _apply_additive_migrations()


def _apply_additive_migrations() -> None:
    """Add any model columns missing from existing tables (additive, safe).

    create_all() won't ALTER existing tables, so a database created with an
    older schema can lack columns the current models declare (e.g. project_id,
    created_at). For each mapped table we diff model columns against the live
    table and ADD COLUMN for any that are missing. New columns are added as
    NULLable so the statement always succeeds on a table that already has rows.
    """
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    try:
        existing_tables = set(inspector.get_table_names())
    except Exception:  # noqa: BLE001
        return

    dialect = engine.dialect
    with engine.begin() as conn:
        for table_name, table in Base.metadata.tables.items():
            if table_name not in existing_tables:
                continue
            live_cols = {c["name"] for c in inspector.get_columns(table_name)}
            for col in table.columns:
                if col.name in live_cols:
                    continue
                try:
                    coltype = col.type.compile(dialect=dialect)
                except Exception:  # noqa: BLE001
                    coltype = "TEXT"
                try:
                    conn.execute(
                        text(
                            f"ALTER TABLE {table_name} "
                            f"ADD COLUMN {col.name} {coltype}"
                        )
                    )
                except Exception:  # noqa: BLE001
                    # Best-effort; never block startup on a single column.
                    pass
