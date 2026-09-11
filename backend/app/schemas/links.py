from datetime import datetime, timezone

from pydantic import BaseModel, Field, field_validator


def _utc(dt: datetime | None) -> datetime | None:
    # SQLite devuelve naive aunque la columna sea timezone-aware; sin zona, el
    # navegador lo lee como hora local y "caduca en 12 h" se convierte en 10.
    return dt.replace(tzinfo=timezone.utc) if dt is not None and dt.tzinfo is None else dt


class VaultPartner(BaseModel):
    id: int
    name: str
    linked_at: datetime
    expires_at: datetime | None = None

    _tz = field_validator("linked_at", "expires_at")(_utc)


class VaultInviteCreate(BaseModel):
    # None = para siempre; 12 = una noche. Tope de un mes por si acaso.
    hours: int | None = Field(None, ge=1, le=24 * 31)


class VaultInviteOut(BaseModel):
    token: str
    expires_at: datetime

    _tz = field_validator("expires_at")(_utc)


class VaultInvitePeek(BaseModel):
    """Lo que ve quien abre el enlace antes de aceptar (o de iniciar sesión)."""
    inviter_id: int
    inviter_name: str
    expires_at: datetime
    hours: int | None = None

    _tz = field_validator("expires_at")(_utc)
