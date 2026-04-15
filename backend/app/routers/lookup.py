import re
import json
from html import unescape
from urllib.parse import unquote, urlparse

import httpx
from fastapi import APIRouter, HTTPException, status

from app.config import settings

router = APIRouter(prefix="/lookup", tags=["lookup"])

YOUTUBE_REGEX = re.compile(
    r"(?:youtu\.be/|youtube\.com/(?:watch\?v=|embed/|shorts/))([A-Za-z0-9_-]{11})"
)

STREAMING_HOST_PATTERNS: dict[str, tuple[str, ...]] = {
    "netflix": ("netflix.com",),
    "prime": ("primevideo.com", "amazon.com"),
    "max": ("max.com", "hbomax.com"),
    "disney": ("disneyplus.com",),
    "stremio": ("strem.io", "stremio.com", "stremio"),
    "spotify": ("open.spotify.com",),
}

# Hosts that should be treated as books for autodetection
BOOK_HOST_PATTERNS: dict[str, tuple[str, ...]] = {
    "openlibrary": ("openlibrary.org",),
    "goodreads": ("goodreads.com",),
    "amazon": ("amazon.com", "amazon.co.uk", "amazon.es", "amazon.de", "amazon.fr", "amazon.it"),
    "googlebooks": ("books.google.com",),
}

PROVIDER_LABELS: dict[str, str] = {
    "netflix": "Netflix",
    "prime": "Prime Video",
    "max": "Max",
    "disney": "Disney+",
    "stremio": "Stremio",
    "spotify": "Spotify",
    "openlibrary": "Open Library",
    "goodreads": "Goodreads",
    "amazon": "Amazon",
    "googlebooks": "Google Books",
}


def _extract_duration_minutes(html: str) -> int:
    """Extract duration from YouTube watch page HTML without requiring API keys."""
    if not html:
        return 0

    # Most common patterns present in watch page payloads.
    for pattern in (
        r'"lengthSeconds":"(\d+)"',
        r'"lengthSeconds":(\d+)',
        r'"approxDurationMs":"(\d+)"',
        r'"approxDurationMs":(\d+)',
    ):
        match = re.search(pattern, html)
        if not match:
            continue

        value = int(match.group(1))
        seconds = value // 1000 if "DurationMs" in pattern else value
        if seconds > 0:
            return seconds // 60

    return 0


def _parse_iso8601_duration_seconds(value: str | None) -> int:
    if not value:
        return 0
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", value)
    if not match:
        return 0
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    return (hours * 3600) + (minutes * 60) + seconds


def _extract_meta_content(html: str, key: str) -> str:
    if not html:
        return ""
    patterns = (
        rf'<meta[^>]+property=["\']{re.escape(key)}["\'][^>]+content=["\']([^"\']+)["\']',
        rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']{re.escape(key)}["\']',
        rf'<meta[^>]+name=["\']{re.escape(key)}["\'][^>]+content=["\']([^"\']+)["\']',
        rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']{re.escape(key)}["\']',
    )
    for pattern in patterns:
        match = re.search(pattern, html, flags=re.IGNORECASE)
        if match:
            return unescape(match.group(1)).strip()
    return ""


def _extract_title_tag(html: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    raw = re.sub(r"\s+", " ", match.group(1)).strip()
    return unescape(raw)


def _extract_jsonld_duration_minutes(html: str) -> int:
    if not html:
        return 0
    blocks = re.findall(
        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    for block in blocks:
        try:
            parsed = json.loads(block.strip())
        except Exception:
            continue

        items = parsed if isinstance(parsed, list) else [parsed]
        for item in items:
            if not isinstance(item, dict):
                continue
            seconds = _parse_iso8601_duration_seconds(item.get("duration"))
            if seconds > 0:
                return seconds // 60
    return 0


def _detect_provider(url: str) -> str | None:
    try:
        hostname = urlparse(url).hostname or ""
    except Exception:
        return None

    host = hostname.lower()
    for provider, patterns in STREAMING_HOST_PATTERNS.items():
        if any(pattern in host for pattern in patterns):
            return provider

    for provider, patterns in BOOK_HOST_PATTERNS.items():
        if any(pattern in host for pattern in patterns):
            return provider

    if "youtube.com" in host or "youtu.be" in host:
        return "youtube"
    if "store.steampowered.com" in host:
        return "steam"
    if "open.spotify.com" in host:
        return "spotify"
    return None
async def lookup_spotify(url: str) -> dict:
    """Lookup Spotify track info using Spotify API."""
    import base64
    import time
    # Soportar track URLs con o sin prefijo de idioma
    match = re.search(r"open\.spotify\.com/(?:[a-zA-Z0-9-]+/)?track/([A-Za-z0-9]+)", url)
    if not match:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Invalid Spotify track URL: {url}")
    track_id = match.group(1)

    # Get OAuth token
    client_id = settings.spotify_client_id
    client_secret = settings.spotify_client_secret
    if not client_id or not client_secret:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Spotify credentials not configured")
    token_url = "https://accounts.spotify.com/api/token"
    auth_header = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    headers = {"Authorization": f"Basic {auth_header}"}
    data = {"grant_type": "client_credentials"}
    async with httpx.AsyncClient(timeout=10) as client:
        token_resp = await client.post(token_url, data=data, headers=headers)
    if token_resp.status_code != 200:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Failed to authenticate with Spotify API")
    token = token_resp.json().get("access_token")
    if not token:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "No access token from Spotify API")

    # Get track info
    api_url = f"https://api.spotify.com/v1/tracks/{track_id}"
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(api_url, headers=headers)
    if resp.status_code != 200:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Track not found on Spotify")
    data = resp.json()
    duration_ms = int(data.get("duration_ms", 0))
    duration_minutes = duration_ms // 60000 if duration_ms > 0 else 0
    artists = ", ".join(artist["name"] for artist in data.get("artists", []))
    thumbnail = ""
    images = data.get("album", {}).get("images", [])
    if images:
        thumbnail = images[0]["url"]
    return {
        "title": data.get("name", ""),
        "author": artists,
        "thumbnail": thumbnail,
        "source_id": track_id,
        "url": url,
        "duration_minutes": duration_minutes,
        "suggested_content_type": "music",
        "provider": "spotify",
    }


@router.get("/book")
async def lookup_book(url: str) -> dict:
    """Lookup book info using Open Library / Google Books as fallbacks."""
    provider = _detect_provider(url)
    if provider not in BOOK_HOST_PATTERNS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unsupported book URL")

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"}, follow_redirects=True)

    html = resp.text if resp.status_code == 200 else ""

    # Prefer structured JSON-LD isbn/title/author if present
    isbn = None
    blocks = re.findall(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html, flags=re.IGNORECASE | re.DOTALL)
    for block in blocks:
        try:
            parsed = json.loads(block.strip())
        except Exception:
            continue
        items = parsed if isinstance(parsed, list) else [parsed]
        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get("isbn"):
                isbn = str(item.get("isbn")).replace("-", "").strip()
                break
        if isbn:
            break

    # meta tags
    if not isbn:
        isbn_meta = _extract_meta_content(html, "isbn") or _extract_meta_content(html, "books:isbn")
        if isbn_meta:
            isbn = isbn_meta.replace("-", "").strip()

    # fallback regex for ISBN-13/10
    if not isbn:
        m = re.search(r"(97[89][\- ]?\d[\d\- ]{8,}\d|\b\d{9}[\dX]\b)", html)
        if m:
            isbn = re.sub(r"[^0-9X]", "", m.group(0))

    title = _extract_meta_content(html, "og:title") or _extract_title_tag(html) or _guess_title_from_url(url)
    author = ""
    thumbnail = ""
    page_count = 0

    # If we have an ISBN, try Open Library first
    if isbn:
        async with httpx.AsyncClient(timeout=10) as client:
            ol = await client.get("https://openlibrary.org/search.json", params={"isbn": isbn})
        if ol.status_code == 200:
            docs = ol.json().get("docs", [])
            if docs:
                doc = docs[0]
                title = doc.get("title") or title
                author = ", ".join(doc.get("author_name", []) or [])
                cover_id = doc.get("cover_i")
                if cover_id:
                    thumbnail = f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg"
                page_count = int(doc.get("number_of_pages_median") or doc.get("number_of_pages") or 0)

    # If still missing info, try Google Books as fallback (no API key required for simple queries)
    if (not title or not author) and isbn:
        async with httpx.AsyncClient(timeout=10) as client:
            gb = await client.get("https://www.googleapis.com/books/v1/volumes", params={"q": f"isbn:{isbn}"})
        if gb.status_code == 200:
            items = gb.json().get("items") or []
            if items:
                info = items[0].get("volumeInfo", {})
                title = info.get("title") or title
                authors = info.get("authors") or []
                author = ", ".join(authors) if authors else author
                page_count = page_count or int(info.get("pageCount") or 0)
                image_links = info.get("imageLinks") or {}
                thumbnail = thumbnail or image_links.get("thumbnail", "")

    # Last resort: search Open Library by title
    if not title and html:
        q = _guess_title_from_url(url)
        if q:
            async with httpx.AsyncClient(timeout=10) as client:
                s = await client.get("https://openlibrary.org/search.json", params={"q": q})
            if s.status_code == 200:
                docs = s.json().get("docs", [])
                if docs:
                    doc = docs[0]
                    title = doc.get("title") or title
                    author = ", ".join(doc.get("author_name", []) or [])
                    cover_id = doc.get("cover_i")
                    if cover_id:
                        thumbnail = f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg"
                    page_count = int(doc.get("number_of_pages_median") or doc.get("number_of_pages") or 0)

    # Estimate reading time from page count (approx 1.2 min/page)
    duration_minutes = int(page_count * 1.2) if page_count and page_count > 0 else 0

    source_id = isbn or _extract_source_id(url, provider) or (title or "").replace(" ", "_")

    return {
        "title": title or "",
        "author": author or PROVIDER_LABELS.get(provider, ""),
        "thumbnail": thumbnail,
        "source_id": source_id,
        "url": url,
        "duration_minutes": duration_minutes,
        "suggested_content_type": "book",
        "provider": provider,
    }


def _guess_title_from_url(url: str) -> str:
    try:
        parsed = urlparse(url)
        path_parts = [p for p in parsed.path.split("/") if p]
        if not path_parts:
            return ""
        candidate = unquote(path_parts[-1])
        if re.fullmatch(r"\d+", candidate):
            return ""
        candidate = re.sub(r"[-_]+", " ", candidate)
        candidate = re.sub(r"\s+", " ", candidate).strip()
        return candidate.title()
    except Exception:
        return ""


def _clean_title(title: str, provider: str) -> str:
    if not title:
        return ""
    cleaned = title
    provider_label = PROVIDER_LABELS.get(provider, "")
    if provider_label:
        cleaned = re.sub(rf"\s*[|\-–—]\s*{re.escape(provider_label)}\s*$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*[|\-–—]\s*(Watch|Streaming|Official Site|Prime Video|Netflix|HBO\s*Max|Max|Disney\+).*$", "", cleaned, flags=re.IGNORECASE)
    # Common streaming CTA prefixes that hurt TMDb matching.
    cleaned = re.sub(
        r"^(watch|ver|voir|guarda|regarder|assistir|disfruta|los\s+episodios\s+completos\s+de|episodios\s+completos\s+de)\s+",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"^(prime\s*video|netflix|hbo\s*max|max|disney\+)\s*[:\-]\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _normalize_text_for_match(value: str) -> str:
    normalized = (value or "").lower().strip()
    normalized = re.sub(r"[\'\"`´]", "", normalized)
    normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def _build_tmdb_query_candidates(title: str, provider: str | None = None) -> list[str]:
    base = (title or "").strip()
    if not base:
        return []

    candidates: list[str] = []

    def add_candidate(value: str) -> None:
        cleaned = re.sub(r"\s+", " ", (value or "").strip())
        if cleaned and cleaned not in candidates:
            candidates.append(cleaned)

    add_candidate(base)
    add_candidate(_clean_title(base, provider or ""))
    add_candidate(re.sub(r"^(prime\s*video|netflix|hbo\s*max|max|disney\+)\s*[:\-]\s*", "", base, flags=re.IGNORECASE))
    add_candidate(
        re.sub(
            r"^(watch|ver|voir|guarda|regarder|assistir|disfruta|los\s+episodios\s+completos\s+de|episodios\s+completos\s+de)\s+",
            "",
            base,
            flags=re.IGNORECASE,
        )
    )

    if ":" in base:
        add_candidate(base.split(":", 1)[1])

    return [c for c in candidates if c]


def _extract_source_id(url: str, provider: str) -> str:
    if provider == "netflix":
        match = re.search(r"netflix\.com/watch/(\d+)", url)
        return match.group(1) if match else ""

    if provider == "prime":
        match = re.search(r"(?:detail|dp|gp/video/detail)/([A-Z0-9]+)", url)
        return match.group(1) if match else ""

    if provider == "disney":
        match = re.search(r"disneyplus\.com/(?:video|movies|series)/([^/?#]+)", url)
        return match.group(1) if match else ""

    if provider == "max":
        match = re.search(r"max\.com/.*/([^/?#]+)$", url)
        return match.group(1) if match else ""

    if provider == "stremio":
        match = re.search(r"stremio(?:://|\.com/)(?:detail/)?(?:movie|series)?/?([A-Za-z0-9:_-]+)", url)
        return match.group(1) if match else ""

    return ""


async def _tmdb_fallback(query: str, provider: str | None = None) -> dict:
    if not settings.tmdb_api_key or not query:
        return {}

    search_queries = _build_tmdb_query_candidates(query, provider)
    if not search_queries:
        return {}

    languages = ("es-ES", "en-US")
    best_match: dict | None = None
    best_score = -1.0
    selected_language = "en-US"

    async with httpx.AsyncClient(timeout=10) as client:
        for search_query in search_queries:
            normalized_query = _normalize_text_for_match(search_query)
            for language in languages:
                resp = await client.get(
                    "https://api.themoviedb.org/3/search/multi",
                    params={
                        "api_key": settings.tmdb_api_key,
                        "query": search_query,
                        "language": language,
                        "include_adult": "false",
                    },
                )
                if resp.status_code != 200:
                    continue

                results = [r for r in resp.json().get("results", []) if r.get("media_type") in {"movie", "tv"}]
                for candidate in results:
                    candidate_title = candidate.get("title") or candidate.get("name") or ""
                    normalized_title = _normalize_text_for_match(candidate_title)
                    exact_score = 120.0 if normalized_title == normalized_query else 0.0
                    contains_score = 50.0 if normalized_query and (normalized_query in normalized_title or normalized_title in normalized_query) else 0.0
                    popularity_score = min(float(candidate.get("popularity") or 0), 60.0)
                    votes_score = min(float(candidate.get("vote_count") or 0) / 200.0, 20.0)
                    total_score = exact_score + contains_score + popularity_score + votes_score

                    if total_score > best_score:
                        best_score = total_score
                        best_match = candidate
                        selected_language = language

        if not best_match:
            return {}

        media_type = best_match.get("media_type")
        item_id = best_match.get("id")
        details_resp = await client.get(
            f"https://api.themoviedb.org/3/{media_type}/{item_id}",
            params={"api_key": settings.tmdb_api_key, "language": selected_language},
        )
        details = details_resp.json() if details_resp.status_code == 200 else {}

    runtime = 0
    if media_type == "movie":
        runtime = int(details.get("runtime") or 0)
    else:
        episodes_runtime = details.get("episode_run_time") or []
        runtime = int(episodes_runtime[0]) if episodes_runtime else 0

    title = best_match.get("title") or best_match.get("name") or query
    poster_path = best_match.get("poster_path") or details.get("poster_path")
    thumbnail = f"https://image.tmdb.org/t/p/w780{poster_path}" if poster_path else ""

    return {
        "title": title,
        "duration_minutes": runtime,
        "thumbnail": thumbnail,
        "source_id": f"tmdb:{media_type}:{item_id}",
        "media_type": media_type,
    }


def _normalize_game_name(name: str) -> str:
    """Normalize game names to improve HowLongToBeat match rates."""
    normalized = re.sub(r"[™®©]", "", name)
    normalized = re.sub(r"\s*:\s*", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.title().strip()


async def _get_hltb_duration_minutes(game_name: str) -> int:
    """Lookup game duration in HLTB and return main-story minutes."""
    if not game_name:
        return 0

    try:
        # Imported lazily so the API can still run before deps are refreshed.
        from howlongtobeatpy import HowLongToBeat
    except Exception:
        return 0

    try:
        hltb = HowLongToBeat()
        normalized = _normalize_game_name(game_name)
        results = await hltb.async_search(normalized)
        if not results:
            results = await hltb.async_search(game_name)
        if not results:
            return 0

        best_match = results[0]
        hours = float(best_match.main_story or 0)
        if hours <= 0:
            return 0
        return int(hours * 60)
    except Exception:
        return 0


@router.get("/youtube")
async def lookup_youtube(url: str) -> dict:
    """Use YouTube oEmbed to get title/author and parse duration from watch page."""
    match = YOUTUBE_REGEX.search(url)
    if not match:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid YouTube URL")

    video_id = match.group(1)
    watch_url = f"https://www.youtube.com/watch?v={video_id}"
    oembed_url = f"https://www.youtube.com/oembed?url={watch_url}&format=json"

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(oembed_url)
        watch_resp = await client.get(
            watch_url,
            headers={"User-Agent": "Mozilla/5.0"},
            follow_redirects=True,
        )

    if resp.status_code != 200:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Video not found")

    data = resp.json()
    duration_minutes = _extract_duration_minutes(watch_resp.text if watch_resp.status_code == 200 else "")

    return {
        "title": data.get("title", ""),
        "author": data.get("author_name", ""),
        "thumbnail": f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
        "source_id": video_id,
        "url": watch_url,
        "duration_minutes": duration_minutes,
    }


@router.get("/steam")
async def lookup_steam(url: str) -> dict:
    """Lookup Steam store page for game info."""
    # Extract app id from store URL
    steam_match = re.search(r"store\.steampowered\.com/app/(\d+)", url)
    if not steam_match:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid Steam URL")
    app_id = steam_match.group(1)
    api_url = f"https://store.steampowered.com/api/appdetails?appids={app_id}&l=spanish"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(api_url)
    if resp.status_code != 200:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Game not found")
    data = resp.json()
    app_data = data.get(app_id, {})
    if not app_data.get("success"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Game not found")
    info = app_data["data"]
    duration_minutes = await _get_hltb_duration_minutes(info.get("name", ""))

    return {
        "title": info.get("name", ""),
        "author": ", ".join(info.get("developers", [])),
        "thumbnail": info.get("header_image", ""),
        "source_id": app_id,
        "url": f"https://store.steampowered.com/app/{app_id}",
        "duration_minutes": duration_minutes,
    }


@router.get("/streaming")
async def lookup_streaming(url: str) -> dict:
    provider = _detect_provider(url)
    if provider not in STREAMING_HOST_PATTERNS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unsupported streaming URL")

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
            follow_redirects=True,
        )

    html = resp.text if resp.status_code == 200 else ""
    title = _extract_meta_content(html, "og:title") or _extract_title_tag(html)
    title = _clean_title(title, provider)
    thumbnail = _extract_meta_content(html, "og:image")

    # Streaming providers often expose trailer/preview lengths in og:video:duration.
    # Prefer JSON-LD first; treat very short OG durations as low confidence.
    jsonld_duration_minutes = _extract_jsonld_duration_minutes(html)
    og_duration_seconds = int(_extract_meta_content(html, "og:video:duration") or 0)
    og_duration_minutes = og_duration_seconds // 60 if og_duration_seconds > 0 else 0
    duration_minutes = jsonld_duration_minutes
    if duration_minutes <= 0 and og_duration_minutes >= 15:
        duration_minutes = og_duration_minutes

    if not title:
        title = _guess_title_from_url(url)

    tmdb = await _tmdb_fallback(title, provider)
    if tmdb:
        # Prefer canonical title from TMDb when available.
        title = tmdb.get("title", title)
        tmdb_duration = int(tmdb.get("duration_minutes") or 0)
        # Replace suspiciously short scraped durations with TMDb runtime when available.
        if tmdb_duration > 0 and (duration_minutes <= 0 or duration_minutes < 15):
            duration_minutes = tmdb_duration
        if not thumbnail:
            thumbnail = tmdb.get("thumbnail", "")

    source_id = _extract_source_id(url, provider) or (tmdb.get("source_id", "") if tmdb else "")

    # Decide suggested content type: prefer TMDb media type (tv -> series, movie -> movie)
    suggested_type = "movie"
    if tmdb:
        media_type = tmdb.get("media_type")
        if media_type == "tv":
            suggested_type = "series"
        else:
            suggested_type = "movie"

    return {
        "title": title,
        "author": PROVIDER_LABELS.get(provider, ""),
        "thumbnail": thumbnail,
        "source_id": source_id,
        "url": url,
        "duration_minutes": duration_minutes,
        "suggested_content_type": suggested_type,
        "provider": provider,
    }


@router.get("/auto")
async def lookup_auto(url: str) -> dict:
    provider = _detect_provider(url)
    if provider == "youtube":
        return await lookup_youtube(url)
    if provider == "steam":
        return await lookup_steam(url)
    if provider == "spotify":
        return await lookup_spotify(url)
    if provider in STREAMING_HOST_PATTERNS:
        return await lookup_streaming(url)
    # Book providers (OpenLibrary, Goodreads, Google Books, Amazon book pages)
    if provider in globals().get("BOOK_HOST_PATTERNS", {}):
        return await lookup_book(url)

    raise HTTPException(
        status.HTTP_400_BAD_REQUEST,
        "Unsupported URL. Try YouTube, Steam, Spotify, Netflix, Prime Video, Max, Disney+, Spotify, Stremio, or book links (OpenLibrary/Goodreads/GoogleBooks).",
    )
