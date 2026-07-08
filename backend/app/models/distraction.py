from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DistractionLog(Base):
    """Tiempo perdido en contenido basura, agregado por día y plataforma."""

    __tablename__ = "distraction_logs"
    __table_args__ = (
        UniqueConstraint("user_id", "date", "platform", name="uq_distraction_user_date_platform"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    # shorts | tiktok | twitter | reels
    platform: Mapped[str] = mapped_column(String(30), nullable=False)
    seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Vídeos/scrolls distintos vistos (shorts, tiktoks, reels)
    items_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    user: Mapped["User"] = relationship()  # noqa: F821
