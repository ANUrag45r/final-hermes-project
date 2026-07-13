from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AutoIngestSettings(Base):
    __tablename__ = "auto_ingest_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    activated_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
