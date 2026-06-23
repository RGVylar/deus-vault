import re
from urllib.parse import urlencode, urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import get_current_user
from app.models.content import Content, ContentType
from app.models.user import User
from app.security import decode_token

STEAM_OPENID_URL = "https://steamcommunity.com/openid/login"

auth_router = APIRouter(prefix="/auth", tags=["steam"])
contents_router = APIRouter(prefix="/contents", tags=["steam"])


@auth_router.get("/steam/login")
async def steam_login(token: str = Query(...), steam_api_key: str | None = Query(None)):
    """Inicia el flujo Steam OpenID. El token JWT se pasa como query param
    porque el navegador navega directamente a esta URL (no puede enviar headers)."""
    effective_key = steam_api_key or settings.steam_api_key
    if not effective_key:
        raise HTTPException(400, "Steam API key no configurada")

    user_id = decode_token(token)
    if user_id is None:
        raise HTTPException(401, "Token inválido")

    parsed = urlparse(settings.steam_callback_url)
    realm = f"{parsed.scheme}://{parsed.netloc}"
    return_to = f"{settings.steam_callback_url}?state={token}"

    params = {
        "openid.ns": "http://specs.openid.net/auth/2.0",
        "openid.mode": "checkid_setup",
        "openid.return_to": return_to,
        "openid.realm": realm,
        "openid.claimed_id": "http://specs.openid.net/auth/2.0/identifier_select",
        "openid.identity": "http://specs.openid.net/auth/2.0/identifier_select",
    }
    return RedirectResponse(f"{STEAM_OPENID_URL}?{urlencode(params)}")


@auth_router.get("/steam/callback")
async def steam_callback(
    request: Request,
    state: str = Query(...),
    db: Session = Depends(get_db),
):
    """Steam redirige aquí tras la autenticación. Verifica la aserción OpenID
    back-channel y guarda el steam_id en el usuario."""
    user_id = decode_token(state)
    if user_id is None:
        raise HTTPException(400, "Token de estado inválido")

    user = db.get(User, int(user_id))
    if user is None:
        raise HTTPException(404, "Usuario no encontrado")

    # Verificación back-channel: reenviar todos los params a Steam con mode=check_authentication
    verify_params = {k: v for k, v in request.query_params.items() if k != "state"}
    verify_params["openid.mode"] = "check_authentication"

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(STEAM_OPENID_URL, data=verify_params)

    if "is_valid:true" not in resp.text:
        raise HTTPException(400, "Verificación con Steam fallida")

    # Extraer steamid64 de openid.claimed_id
    claimed_id = verify_params.get("openid.claimed_id", "")
    match = re.search(r"/openid/id/(\d+)$", claimed_id)
    if not match:
        raise HTTPException(400, "No se pudo extraer el Steam ID")

    user.steam_id = match.group(1)
    db.commit()

    return HTMLResponse(
        f'<html><head><meta http-equiv="refresh" content="0;url={settings.steam_frontend_url}/settings?steam=connected"></head>'
        f'<body>Conectado con Steam. Redirigiendo…</body></html>'
    )


@auth_router.delete("/steam/disconnect")
def steam_disconnect(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user.steam_id = None
    db.commit()
    return {"ok": True}


@contents_router.post("/steam/sync")
async def steam_sync(
    create_new: bool = Query(False, description="Crear entradas nuevas para juegos no presentes en el vault"),
    steam_api_key: str | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Sincroniza el tiempo real de juego de Steam con los juegos del vault.
    Busca por source_id = 'steam_{appid}'."""
    effective_key = steam_api_key or settings.steam_api_key
    if not user.steam_id:
        raise HTTPException(400, "Cuenta de Steam no conectada")
    if not effective_key:
        raise HTTPException(400, "Steam API key no configurada")

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            "https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/",
            params={
                "key": effective_key,
                "steamid": user.steam_id,
                "include_appinfo": "true",
                "include_played_free_games": "true",
            },
        )
        resp.raise_for_status()

    games = resp.json().get("response", {}).get("games", [])
    synced = 0
    created = 0

    for game in games:
        appid = game.get("appid")
        playtime = game.get("playtime_forever", 0)
        if not appid or playtime <= 0:
            continue

        source_id = f"steam_{appid}"
        existing = db.scalars(
            select(Content).where(Content.user_id == user.id, Content.source_id == source_id)
        ).first()

        if existing:
            existing.duration_minutes = playtime
            synced += 1
        elif create_new:
            name = game.get("name", f"Steam Game {appid}")
            icon = game.get("img_icon_url")
            thumbnail = (
                f"https://media.steampowered.com/steamcommunity/public/images/apps/{appid}/{icon}.jpg"
                if icon else None
            )
            db.add(Content(
                user_id=user.id,
                title=name,
                content_type=ContentType.game,
                source_id=source_id,
                duration_minutes=playtime,
                thumbnail=thumbnail,
                consumed=False,
            ))
            created += 1

    db.commit()
    return {"synced": synced, "created": created, "total_steam_games": len(games)}


@contents_router.get("/steam/library")
async def steam_library(
    steam_api_key: str | None = Query(None),
    user: User = Depends(get_current_user),
):
    """Devuelve la biblioteca de Steam del usuario (juegos con tiempo jugado > 0)."""
    effective_key = steam_api_key or settings.steam_api_key
    if not user.steam_id:
        raise HTTPException(400, "Cuenta de Steam no conectada")
    if not effective_key:
        raise HTTPException(400, "Steam API key no configurada")

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            "https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/",
            params={
                "key": effective_key,
                "steamid": user.steam_id,
                "include_appinfo": "true",
                "include_played_free_games": "true",
            },
        )
        resp.raise_for_status()

    games = resp.json().get("response", {}).get("games", [])
    return [
        {
            "appid": g["appid"],
            "name": g.get("name", ""),
            "playtime_forever": g.get("playtime_forever", 0),
            "source_id": f"steam_{g['appid']}",
            "thumbnail": (
                f"https://media.steampowered.com/steamcommunity/public/images/apps/{g['appid']}/{g['img_icon_url']}.jpg"
                if g.get("img_icon_url") else None
            ),
        }
        for g in games
        if g.get("playtime_forever", 0) > 0
    ]
