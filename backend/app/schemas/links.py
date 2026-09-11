from datetime import datetime

from pydantic import BaseModel


class VaultPartner(BaseModel):
    id: int
    name: str
    linked_at: datetime


class VaultInviteOut(BaseModel):
    token: str
    expires_at: datetime


class VaultInvitePeek(BaseModel):
    """Lo que ve quien abre el enlace antes de aceptar (o de iniciar sesión)."""
    inviter_id: int
    inviter_name: str
    expires_at: datetime
