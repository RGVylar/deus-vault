import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.models.vault_link import VaultInvite, VaultLink
from app.schemas.links import VaultInviteOut, VaultInvitePeek, VaultPartner

router = APIRouter(prefix="/links", tags=["links"])

INVITE_TTL = timedelta(hours=48)


def _pair(a: int, b: int) -> tuple[int, int]:
    return (a, b) if a < b else (b, a)


def _links_of(db: Session, user_id: int) -> list[VaultLink]:
    return list(db.scalars(
        select(VaultLink).where(or_(VaultLink.user_a_id == user_id, VaultLink.user_b_id == user_id))
    ).all())


def _partner_of(link: VaultLink, user_id: int) -> User:
    return link.user_b if link.user_a_id == user_id else link.user_a


def linked_user_ids(db: Session, user_id: int) -> set[int]:
    """Ids de los usuarios con los que `user_id` tiene la bóveda enlazada.
    Lo usa la ruleta para validar `with_user` antes de ampliar el pool."""
    return {
        link.user_b_id if link.user_a_id == user_id else link.user_a_id
        for link in _links_of(db, user_id)
    }


def _to_partner(link: VaultLink, user_id: int) -> VaultPartner:
    partner = _partner_of(link, user_id)
    return VaultPartner(id=partner.id, name=partner.name, linked_at=link.created_at)


def _live_invite(db: Session, token: str) -> VaultInvite:
    invite = db.scalar(select(VaultInvite).where(VaultInvite.token == token))
    if invite is None or invite.used_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invite not found")
    expires_at = invite.expires_at
    if expires_at.tzinfo is None:
        # SQLite devuelve naive aunque la columna sea timezone-aware
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invite expired")
    return invite


@router.get("", response_model=list[VaultPartner])
def list_links(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[VaultPartner]:
    return [_to_partner(link, user.id) for link in _links_of(db, user.id)]


@router.post("/invite", response_model=VaultInviteOut, status_code=status.HTTP_201_CREATED)
def create_invite(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> VaultInviteOut:
    """Genera un enlace de invitación de un solo uso. Cada llamada crea uno
    nuevo: reenviar un WhatsApp viejo no debe enlazar a nadie por accidente."""
    invite = VaultInvite(
        token=secrets.token_urlsafe(9),  # 12 chars, legible en una URL corta
        inviter_id=user.id,
        expires_at=datetime.now(timezone.utc) + INVITE_TTL,
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)
    return VaultInviteOut(token=invite.token, expires_at=invite.expires_at)


@router.get("/invite/{token}", response_model=VaultInvitePeek)
def peek_invite(token: str, db: Session = Depends(get_db)) -> VaultInvitePeek:
    """Público a propósito: quien abre el enlace ve quién le invita antes de
    tener que iniciar sesión o registrarse. Sólo expone el nombre."""
    invite = _live_invite(db, token)
    return VaultInvitePeek(inviter_id=invite.inviter_id, inviter_name=invite.inviter.name, expires_at=invite.expires_at)


@router.post("/invite/{token}/accept", response_model=VaultPartner)
def accept_invite(
    token: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> VaultPartner:
    invite = _live_invite(db, token)
    if invite.inviter_id == user.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot accept your own invite")

    a, b = _pair(user.id, invite.inviter_id)
    link = db.scalar(select(VaultLink).where(VaultLink.user_a_id == a, VaultLink.user_b_id == b))
    if link is None:
        link = VaultLink(user_a_id=a, user_b_id=b)
        db.add(link)
    # Ya enlazados: aceptar es idempotente, pero el token se quema igual.
    invite.used_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(link)
    return _to_partner(link, user.id)


@router.delete("/{partner_id}", status_code=status.HTTP_204_NO_CONTENT)
def unlink(
    partner_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    a, b = _pair(user.id, partner_id)
    link = db.scalar(select(VaultLink).where(VaultLink.user_a_id == a, VaultLink.user_b_id == b))
    if link is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Link not found")
    db.delete(link)
    db.commit()
