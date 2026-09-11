from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class VaultLink(Base):
    """Dos usuarios que han enlazado sus bóvedas: la ruleta puede tirar de las
    dos a la vez. La pareja se guarda ordenada (user_a_id < user_b_id) para que
    la restricción de unicidad baste y no haya que buscar en los dos sentidos."""

    __tablename__ = "vault_links"
    __table_args__ = (UniqueConstraint("user_a_id", "user_b_id", name="uq_vault_link_pair"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_a_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    user_b_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    # None = para siempre. Con fecha, el enlace se rompe solo al pasar (una noche).
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user_a: Mapped["User"] = relationship(foreign_keys=[user_a_id])  # noqa: F821
    user_b: Mapped["User"] = relationship(foreign_keys=[user_b_id])  # noqa: F821


class VaultInvite(Base):
    """Invitación de un solo uso que viaja en una URL (WhatsApp, Telegram…).
    Quien la abre y la acepta queda enlazado con quien la creó."""

    __tablename__ = "vault_invites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    inviter_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Cuánto dura el enlace que crea al aceptarse. None = para siempre.
    link_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    inviter: Mapped["User"] = relationship()  # noqa: F821
