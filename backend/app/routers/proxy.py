"""Same-origin image proxy for the Rewind share canvas.

A canvas that draws an image from another domain without CORS permission gets
tainted, and then `toBlob` fails: you lose the whole share image, not just one
thumbnail. Loading with `crossOrigin` avoids the tainting but silently drops
every cover whose host doesn't send `Access-Control-Allow-Origin` (TMDB does,
plenty of others don't). Serving the bytes from our own domain sidesteps CORS
entirely.

Only the hosts our own lookups produce are allowed through: an endpoint that
fetches arbitrary URLs from the server is an SSRF hole.
"""

from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.deps import get_current_user
from app.models.user import User

router = APIRouter(prefix="/proxy", tags=["proxy"])

# Domains behind the thumbnails we store: TMDB posters, YouTube video
# thumbnails and channel avatars, OpenLibrary covers (which redirect to
# archive.org), Steam game art, Spotify album art. Subdomains are allowed
# because these CDNs shard across them (ia600304.us.archive.org, i9.ytimg.com).
ALLOWED_DOMAINS: tuple[str, ...] = (
    "tmdb.org",
    "youtube.com",
    "ytimg.com",
    "ggpht.com",
    "googleusercontent.com",
    "openlibrary.org",
    "archive.org",
    "steampowered.com",
    "steamstatic.com",
    "scdn.co",
    # Streaming artwork: these don't come from our lookups but from the
    # extension or manual entries, so a poster can be on any provider's CDN.
    "warnermediacdn.com",   # Max / HBO
    "nflxso.net",           # Netflix
    "media-amazon.com",     # Prime Video
    "disney-plus.net",      # Disney+
    "crunchyroll.com",
    "mzstatic.com",         # Apple TV+
)

# Hosts allowed on their own, where opening up the whole domain would be too much.
ALLOWED_HOSTS: frozenset[str] = frozenset(
    {
        "books.google.com",
        "steamcdn-a.akamaihd.net",
    }
)

MAX_BYTES = 8 * 1024 * 1024
MAX_REDIRECTS = 3


def _check(url: str) -> None:
    """Reject anything that isn't https on an allow-listed host."""
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only https URLs are allowed")
    host = (parsed.hostname or "").lower()
    # The leading dot matters: without it "eviltmdb.org" would pass as tmdb.org.
    allowed = host in ALLOWED_HOSTS or any(
        host == d or host.endswith("." + d) for d in ALLOWED_DOMAINS
    )
    if not allowed:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Host not allowed: {host}")


@router.get("/image")
async def proxy_image(
    url: str = Query(..., max_length=2048),
    user: User = Depends(get_current_user),
) -> Response:
    _check(url)

    # Redirects are followed by hand so every hop is checked too — otherwise an
    # allowed host could bounce us anywhere.
    async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
        current = url
        for _ in range(MAX_REDIRECTS + 1):
            try:
                res = await client.get(current, headers={"User-Agent": "deus-vault/1.0"})
            except httpx.HTTPError:
                raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Could not fetch image")

            if res.is_redirect:
                location = res.headers.get("location")
                if not location:
                    raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Redirect without location")
                current = str(res.url.join(location))
                _check(current)
                continue
            break
        else:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Too many redirects")

    if res.status_code != 200:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Upstream returned {res.status_code}")

    content_type = res.headers.get("content-type", "").split(";")[0].strip().lower()
    if not content_type.startswith("image/"):
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Not an image: {content_type or 'unknown'}")
    if len(res.content) > MAX_BYTES:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Image too large")

    return Response(
        content=res.content,
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )
