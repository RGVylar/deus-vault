import html
import re
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.models.vault_link import VaultInvite, VaultLink
from app.schemas.links import VaultInviteCreate, VaultInviteOut, VaultInvitePeek, VaultPartner

router = APIRouter(prefix="/links", tags=["links"])
# Fuera de /api: Caddy manda /link/* aquí para que el enlace compartido lleve
# su propia tarjeta (título con el nombre, imagen grande) en vez de la genérica.
page_router = APIRouter(tags=["links"])

INVITE_TTL = timedelta(hours=48)


def _pair(a: int, b: int) -> tuple[int, int]:
    return (a, b) if a < b else (b, a)


def _links_of(db: Session, user_id: int) -> list[VaultLink]:
    """Enlaces vivos del usuario. Los de una noche que ya pasaron se dan por
    rotos aquí mismo, sin cron: basta con no devolverlos nunca."""
    now = datetime.now(timezone.utc)
    return list(db.scalars(
        select(VaultLink).where(
            or_(VaultLink.user_a_id == user_id, VaultLink.user_b_id == user_id),
            or_(VaultLink.expires_at.is_(None), VaultLink.expires_at > now),
        )
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
    return VaultPartner(id=partner.id, name=partner.name, linked_at=link.created_at, expires_at=link.expires_at)


def _as_utc(dt: datetime) -> datetime:
    # SQLite devuelve naive aunque la columna sea timezone-aware
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _live_invite(db: Session, token: str) -> VaultInvite:
    invite = db.scalar(select(VaultInvite).where(VaultInvite.token == token))
    if invite is None or invite.used_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invite not found")
    if _as_utc(invite.expires_at) < datetime.now(timezone.utc):
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
    payload: VaultInviteCreate | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> VaultInviteOut:
    """Genera un enlace de invitación de un solo uso. Cada llamada crea uno
    nuevo: reenviar un WhatsApp viejo no debe enlazar a nadie por accidente.
    `hours` fija cuánto durará el enlace una vez aceptado (None = para siempre)."""
    invite = VaultInvite(
        token=secrets.token_urlsafe(9),  # 12 chars, legible en una URL corta
        inviter_id=user.id,
        expires_at=datetime.now(timezone.utc) + INVITE_TTL,
        link_hours=payload.hours if payload else None,
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
    return VaultInvitePeek(
        inviter_id=invite.inviter_id, inviter_name=invite.inviter.name,
        expires_at=invite.expires_at, hours=invite.link_hours,
    )


@router.post("/invite/{token}/accept", response_model=VaultPartner)
def accept_invite(
    token: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> VaultPartner:
    invite = _live_invite(db, token)
    if invite.inviter_id == user.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot accept your own invite")

    now = datetime.now(timezone.utc)
    a, b = _pair(user.id, invite.inviter_id)
    link = db.scalar(select(VaultLink).where(VaultLink.user_a_id == a, VaultLink.user_b_id == b))
    if link is None:
        link = VaultLink(user_a_id=a, user_b_id=b)
        db.add(link)
    elif link.expires_at is not None and _as_utc(link.expires_at) < now:
        link.created_at = now  # revivir una fila caducada cuenta como enlace nuevo
    # Ya enlazados (o enlace de una noche caducado que sigue en la tabla):
    # mandan las condiciones de la invitación nueva. El token se quema igual.
    link.expires_at = now + timedelta(hours=invite.link_hours) if invite.link_hours else None
    invite.used_at = now
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


# ---------------------------------------------------------------------------
# /link/{token} — el index.html del build con las OpenGraph de la invitación
# ---------------------------------------------------------------------------

_OG_TEXT = {
    "es": {
        "title": "{name} quiere enlazar su bóveda contigo",
        "desc": "Acepta y en Azar podréis tirar de las dos bóvedas a la vez. Un solo uso.",
        "night": " Solo por esta noche.",
        "dead_title": "Deus Vault · Enlace caducado",
        "dead_desc": "Este enlace ya no vale: o caducó, o ya se usó.",
    },
    "en": {
        "title": "{name} wants to link vaults with you",
        "desc": "Accept and in Random you can both roll over the two vaults at once. Single use.",
        "night": " Just for tonight.",
        "dead_title": "Deus Vault · Link expired",
        "dead_desc": "This link no longer works: it expired or was already used.",
    },
    "pt": {
        "title": "{name} quer vincular o cofre com você",
        "desc": "Aceite e em Aleatório vocês podem girar sobre os dois cofres ao mesmo tempo. Uso único.",
        "night": " Só por esta noite.",
        "dead_title": "Deus Vault · Link expirado",
        "dead_desc": "Este link já não vale: expirou ou já foi usado.",
    },
}

_FALLBACK_HTML = """<!doctype html><html lang="es"><head><meta charset="utf-8">
<title>Deus Vault</title>
<meta property="og:title" content="Deus Vault">
<meta property="og:description" content="">
<meta property="og:image" content="">
<meta property="og:url" content="">
<meta name="twitter:card" content="summary_large_image">
</head><body><a href="/">Deus Vault</a></body></html>"""


def _index_html() -> str:
    p = Path(settings.frontend_build_dir) / "index.html"
    try:
        return p.read_text(encoding="utf-8")
    except OSError:
        # Sin build (dev): una cáscara mínima con las mismas etiquetas.
        return _FALLBACK_HTML


def _set_meta(doc: str, key: str, value: str) -> str:
    """Sustituye el content de <meta property|name="key"> (o lo añade si no está)."""
    safe = html.escape(value, quote=True)
    pat = re.compile(r'(<meta\s+(?:property|name)="' + re.escape(key) + r'"\s+content=")[^"]*(")')
    if pat.search(doc):
        return pat.sub(lambda m: m.group(1) + safe + m.group(2), doc, count=1)
    attr = "name" if key.startswith("twitter:") else "property"
    return doc.replace("</head>", f'<meta {attr}="{key}" content="{safe}" />\n</head>', 1)


@page_router.get("/link/{token}", response_class=HTMLResponse, include_in_schema=False)
def invite_page(token: str, request: Request, l: str = "es", db: Session = Depends(get_db)) -> HTMLResponse:
    text = _OG_TEXT.get(l, _OG_TEXT["es"])
    # Tras Cloudflare/Caddy el request llega en http y Caddy pisa X-Forwarded-Proto
    # con "http", así que no hay cabecera fiable: la URL pública es https siempre
    # salvo en desarrollo local.
    host = request.headers.get("host") or request.url.netloc
    proto = "http" if host.split(":")[0] in ("localhost", "127.0.0.1") else "https"
    origin = f"{proto}://{host}"
    try:
        invite = _live_invite(db, token)
        title = text["title"].format(name=invite.inviter.name)
        desc = text["desc"] + (text["night"] if invite.link_hours else "")
        image = f"{origin}/og-link.jpg"
    except HTTPException:
        title, desc, image = text["dead_title"], text["dead_desc"], f"{origin}/og.jpg"

    doc = _index_html()
    doc = re.sub(r"<title>[^<]*</title>", f"<title>{html.escape(title)}</title>", doc, count=1)
    for key, value in (
        ("og:title", title),
        ("og:description", desc),
        ("og:image", image),
        ("og:url", f"{origin}/link/{token}"),
        ("twitter:card", "summary_large_image"),
        ("twitter:title", title),
        ("twitter:description", desc),
        ("twitter:image", image),
    ):
        doc = _set_meta(doc, key, value)
    # Igual que index.html en Caddy: los bots y el navegador deben pedirla siempre.
    return HTMLResponse(doc, headers={"Cache-Control": "no-cache, must-revalidate"})
