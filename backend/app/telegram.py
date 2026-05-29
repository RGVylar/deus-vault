"""Telegram error notifications for Deus Vault."""

import httpx
import traceback
import logging

logger = logging.getLogger(__name__)


async def send_telegram(message: str, token: str, chat_id: str) -> None:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(url, json={
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "HTML",
            })
    except Exception as e:
        logger.warning("Failed to send Telegram notification: %s", e)


async def notify_error(exc: Exception, context: str = "") -> None:
    from app.config import settings
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        return

    tb = traceback.format_exc()[-2000:]  # cap at 2000 chars
    ctx = f"\n<b>Contexto:</b> {context}" if context else ""
    message = (
        f"🔴 <b>Deus Vault — error</b>{ctx}\n\n"
        f"<b>{type(exc).__name__}:</b> {exc}\n\n"
        f"<pre>{tb}</pre>"
    )
    await send_telegram(message, settings.telegram_bot_token, settings.telegram_chat_id)
