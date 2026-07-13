"""AutoSendSettings model for automatically sending meeting report PDFs."""
from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AutoSendSettings(Base):
    __tablename__ = "auto_send_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    target_email: Mapped[str] = mapped_column(String(255), default="")
    email_provider: Mapped[str] = mapped_column(String(64), default="gmail")
