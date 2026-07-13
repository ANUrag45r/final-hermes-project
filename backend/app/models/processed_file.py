from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ProcessedFile(Base):
    __tablename__ = "processed_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    filepath: Mapped[str] = mapped_column(String(1024), unique=True, index=True)
    processed_at: Mapped[str] = mapped_column(String(64))
    meeting_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
