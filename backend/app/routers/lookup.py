import re
import json
import math
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
async def lookup_spotify(url: str, spotify_client_id: str | None = None, spotify_client_secret: str | None = None) -> dict:
    """Lookup Spotify track info using Spotify API."""
    import base64
    # Soportar track URLs con o sin prefijo de idioma
    match = re.search(r"open\.spotify\.com/(?:[a-zA-Z0-9-]+/)?track/([A-Za-z0-9]+)", url)
    if not match:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Invalid Spotify track URL: {url}")
    track_id = match.group(1)

    # Get OAuth token — prefer user-supplied credentials over server config
    client_id = spotify_client_id or settings.spotify_client_id
    client_secret = spotify_client_secret or settings.spotify_client_secret
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

    # For Google Books URLs, extract volume ID and query API directly
    if provider == "googlebooks":
        from urllib.parse import parse_qs
        qs = parse_qs(urlparse(url).query)
        volume_id = (qs.get("id") or [""])[0]
        if volume_id:
            async with httpx.AsyncClient(timeout=10) as client:
                gb_direct = await client.get(f"https://www.googleapis.com/books/v1/volumes/{volume_id}")
            if gb_direct.status_code == 200:
                body = gb_direct.json()
                info = body.get("volumeInfo") or {}
                gb_title = info.get("title", "")
                gb_authors = info.get("authors") or []
                gb_author = ", ".join(gb_authors)
                gb_pages = int(info.get("pageCount") or 0)
                image_links = info.get("imageLinks") or {}
                gb_thumb = image_links.get("thumbnail", "")
                gb_isbn = ""
                for id_entry in info.get("industryIdentifiers") or []:
                    if id_entry.get("type") in ("ISBN_13", "ISBN_10"):
                        gb_isbn = id_entry.get("identifier", "").replace("-", "")
                        break
                words_per_page = int(getattr(settings, "words_per_page", 300) or 300)
                reading_wpm = int(getattr(settings, "reading_speed_wpm", 200) or 200)
                gb_duration = math.ceil(gb_pages * words_per_page / max(1, reading_wpm)) if gb_pages > 0 else 0
                # Return even if title is empty — better than falling through to generic HTML scraping
                return {
                    "title": gb_title,
                    "author": gb_author,
                    "thumbnail": gb_thumb,
                    "page_count": gb_pages,
                    "source_id": gb_isbn or volume_id,
                    "url": url,
                    "duration_minutes": gb_duration,
                    "suggested_content_type": "book",
                    "provider": provider,
                }
            # API failed (403/429/etc.) — at minimum return the volume_id so it's not empty
            return {
                "title": "",
                "author": "",
                "thumbnail": "",
                "page_count": 0,
                "source_id": volume_id,
                "url": url,
                "duration_minutes": 0,
                "suggested_content_type": "book",
                "provider": provider,
            }

    # Prefer structured JSON-LD isbn/title/author if present
    isbn = None
    jsonld_author = ""
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
            # Extract author from JSON-LD (Goodreads, OpenLibrary, etc.)
            if not jsonld_author:
                author_data = item.get("author")
                if isinstance(author_data, dict):
                    jsonld_author = author_data.get("name", "")
                elif isinstance(author_data, list):
                    jsonld_author = ", ".join(
                        a.get("name", "") for a in author_data if isinstance(a, dict) and a.get("name")
                    )
        if isbn and jsonld_author:
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
    author = jsonld_author
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
                author = ", ".join(doc.get("author_name", []) or []) or author
                cover_id = doc.get("cover_i")
                if cover_id:
                    thumbnail = f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg"
                # Prefer numeric page counts, fall back to parsing pagination strings
                page_count = 0
                try:
                    np_candidate = doc.get("number_of_pages_median") or doc.get("number_of_pages")
                    if np_candidate:
                        page_count = int(np_candidate)
                except Exception:
                    page_count = 0
                if page_count == 0:
                    pag = doc.get("pagination") or doc.get("pages") or ""
                    if pag:
                        m = re.search(r"(\d{2,5})", str(pag))
                        if m:
                            try:
                                page_count = int(m.group(1))
                            except Exception:
                                page_count = 0

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

    # If we still don't have page count but have an ISBN, try Google Books specifically
    if page_count == 0 and isbn:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                gb2 = await client.get("https://www.googleapis.com/books/v1/volumes", params={"q": f"isbn:{isbn}"})
            if gb2.status_code == 200:
                items = gb2.json().get("items") or []
                if items:
                    info = items[0].get("volumeInfo", {})
                    page_count = page_count or int(info.get("pageCount") or 0)
                    image_links = info.get("imageLinks") or {}
                    thumbnail = thumbnail or image_links.get("thumbnail", "")
        except Exception:
            pass

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
                    # Try numeric page fields first, then parse pagination text
                    try:
                        page_count = int(doc.get("number_of_pages_median") or doc.get("number_of_pages") or 0)
                    except Exception:
                        page_count = 0
                    if page_count == 0:
                        pag = doc.get("pagination") or doc.get("pages") or ""
                        if pag:
                            m = re.search(r"(\d{2,5})", str(pag))
                            if m:
                                try:
                                    page_count = int(m.group(1))
                                except Exception:
                                    page_count = 0

    # If this is an Open Library work page and we still don't have page_count,
    # try fetching editions for the work and derive a median page count from editions.
    if provider == "openlibrary" and page_count == 0:
        try:
            parsed = urlparse(url)
            parts = [p for p in parsed.path.split("/") if p]
            if parts and parts[0] == "works" and len(parts) >= 2:
                work_id = parts[1]
                async with httpx.AsyncClient(timeout=10) as client:
                    editions_resp = await client.get(f"https://openlibrary.org/works/{work_id}/editions.json", params={"limit": 50})
                if editions_resp.status_code == 200:
                    entries = editions_resp.json().get("entries") or editions_resp.json().get("docs") or []
                    counts: list[int] = []
                    for e in entries:
                        np = 0
                        try:
                            num = e.get("number_of_pages")
                            if num:
                                np = int(num)
                            else:
                                pag = e.get("pagination") or e.get("pages") or ""
                                if pag:
                                    m = re.search(r"(\d{2,5})", str(pag))
                                    if m:
                                        try:
                                            np = int(m.group(1))
                                        except Exception:
                                            np = 0
                        except Exception:
                            np = 0
                        if np and np > 0:
                            counts.append(np)
                    if counts:
                        counts.sort()
                        mid = len(counts) // 2
                        page_count = int(counts[mid] if len(counts) % 2 == 1 else (counts[mid - 1] + counts[mid]) // 2)
        except Exception:
            pass

    # If still missing page_count/thumbnail but we have title+author, search Open Library by title
    if (not page_count or not thumbnail) and title:
        try:
            search_params: dict = {"title": title}
            if author:
                search_params["author"] = author.split(",")[0].strip()
            async with httpx.AsyncClient(timeout=10) as client:
                ol_title = await client.get("https://openlibrary.org/search.json", params=search_params)
            if ol_title.status_code == 200:
                docs = ol_title.json().get("docs", [])
                if docs:
                    doc = docs[0]
                    if not page_count:
                        try:
                            page_count = int(doc.get("number_of_pages_median") or doc.get("number_of_pages") or 0)
                        except Exception:
                            page_count = 0
                    if not author:
                        author = ", ".join(doc.get("author_name", []) or [])
                    if not thumbnail:
                        cover_id = doc.get("cover_i")
                        if cover_id:
                            thumbnail = f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg"
        except Exception:
            pass

    # Estimate reading time from page count using configured reading speed.
    duration_minutes = 0
    if page_count and page_count > 0:
        words_per_page = int(getattr(settings, "words_per_page", 300) or 300)
        reading_wpm = int(getattr(settings, "reading_speed_wpm", 200) or 200)
        words_total = page_count * words_per_page
        duration_minutes = math.ceil(words_total / max(1, reading_wpm))

    source_id = isbn or _extract_source_id(url, provider) or (title or "").replace(" ", "_")

    return {
        "title": title or "",
        "author": author or PROVIDER_LABELS.get(provider, ""),
        "thumbnail": thumbnail,
        "page_count": page_count,
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
        # Extract IMDb ID from hash-based SPA URLs (e.g. app.strem.io/shell-v4.4/#/detail/movie/tt0780504/...)
        imdb_match = re.search(r"\b(tt\d{7,})\b", url)
        if imdb_match:
            return imdb_match.group(1)
        match = re.search(r"stremio(?:://|\.com/)(?:detail/)?(?:movie|series)?/?([A-Za-z0-9:_-]+)", url)
        return match.group(1) if match else ""

    return ""


async def _tmdb_find_by_imdb(imdb_id: str, api_key: str) -> dict:
    """Look up a movie or series on TMDb using an IMDb ID via the /find endpoint."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"https://api.themoviedb.org/3/find/{imdb_id}",
            params={"api_key": api_key, "external_source": "imdb_id"},
        )
        if resp.status_code != 200:
            return {}
        data = resp.json()
        movie_results = data.get("movie_results") or []
        tv_results = data.get("tv_results") or []

        if movie_results:
            item = movie_results[0]
            media_type = "movie"
        elif tv_results:
            item = tv_results[0]
            media_type = "tv"
        else:
            return {}

        item_id = item.get("id")
        details_resp = await client.get(
            f"https://api.themoviedb.org/3/{media_type}/{item_id}",
            params={"api_key": api_key, "language": "es-ES"},
        )
        details = details_resp.json() if details_resp.status_code == 200 else {}

    runtime = 0
    episode_count: int | None = None
    seasons: int | None = None
    if media_type == "movie":
        runtime = int(details.get("runtime") or 0)
    else:
        episodes_runtime = details.get("episode_run_time") or []
        runtime = int(episodes_runtime[0]) if episodes_runtime else 0
        if not runtime:
            last_ep = details.get("last_episode_to_air") or {}
            runtime = int(last_ep.get("runtime") or 0)
        ep_total = details.get("number_of_episodes")
        seasons_total = details.get("number_of_seasons")
        if ep_total:
            episode_count = int(ep_total)
        if seasons_total:
            seasons = int(seasons_total)

    title = details.get("title") or details.get("name") or item.get("title") or item.get("name") or ""
    poster_path = details.get("poster_path") or item.get("poster_path")
    thumbnail = f"https://image.tmdb.org/t/p/w780{poster_path}" if poster_path else ""

    return {
        "title": title,
        "duration_minutes": runtime,
        "thumbnail": thumbnail,
        "source_id": f"tmdb:{media_type}:{item_id}",
        "media_type": media_type,
        "episode_count": episode_count,
        "seasons": seasons,
    }


async def _tmdb_fallback(query: str, provider: str | None = None, tmdb_api_key: str | None = None) -> dict:
    api_key = tmdb_api_key or settings.tmdb_api_key
    if not api_key or not query:
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
                        "api_key": api_key,
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
            params={"api_key": api_key, "language": selected_language},
        )
        details = details_resp.json() if details_resp.status_code == 200 else {}

    runtime = 0
    episode_count: int | None = None
    seasons: int | None = None
    if media_type == "movie":
        runtime = int(details.get("runtime") or 0)
    else:
        episodes_runtime = details.get("episode_run_time") or []
        runtime = int(episodes_runtime[0]) if episodes_runtime else 0
        if not runtime:
            last_ep = details.get("last_episode_to_air") or {}
            runtime = int(last_ep.get("runtime") or 0)
        ep_total = details.get("number_of_episodes")
        seasons_total = details.get("number_of_seasons")
        if ep_total:
            episode_count = int(ep_total)
        if seasons_total:
            seasons = int(seasons_total)

    title = best_match.get("title") or best_match.get("name") or query
    poster_path = best_match.get("poster_path") or details.get("poster_path")
    thumbnail = f"https://image.tmdb.org/t/p/w780{poster_path}" if poster_path else ""

    return {
        "title": title,
        "duration_minutes": runtime,
        "thumbnail": thumbnail,
        "source_id": f"tmdb:{media_type}:{item_id}",
        "media_type": media_type,
        "episode_count": episode_count,
        "seasons": seasons,
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
async def lookup_streaming(url: str, tmdb_api_key: str | None = None) -> dict:
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

    # For Stremio URLs containing an IMDb ID, use TMDb /find for accurate results
    effective_tmdb_key = tmdb_api_key or settings.tmdb_api_key
    stremio_imdb_id = _extract_source_id(url, provider) if provider == "stremio" else ""
    if stremio_imdb_id and re.match(r"tt\d{7,}", stremio_imdb_id) and effective_tmdb_key:
        tmdb = await _tmdb_find_by_imdb(stremio_imdb_id, effective_tmdb_key)
    else:
        tmdb = await _tmdb_fallback(title, provider, tmdb_api_key=tmdb_api_key)
    episode_count: int | None = None
    seasons: int | None = None
    if tmdb:
        # Prefer canonical title from TMDb when available.
        title = tmdb.get("title", title)
        tmdb_duration = int(tmdb.get("duration_minutes") or 0)
        # Replace suspiciously short scraped durations with TMDb runtime when available.
        if tmdb_duration > 0 and (duration_minutes <= 0 or duration_minutes < 15):
            duration_minutes = tmdb_duration
        if not thumbnail:
            thumbnail = tmdb.get("thumbnail", "")
        if tmdb.get("episode_count"):
            episode_count = int(tmdb["episode_count"])
        if tmdb.get("seasons"):
            seasons = int(tmdb["seasons"])

    extracted_source_id = _extract_source_id(url, provider)
    # For Stremio, prefer the IMDb ID (used in stremio:// protocol URLs)
    if provider == "stremio" and stremio_imdb_id:
        source_id = stremio_imdb_id
    else:
        source_id = extracted_source_id or (tmdb.get("source_id", "") if tmdb else "")

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
        "episode_count": episode_count,
        "seasons": seasons,
        "suggested_content_type": suggested_type,
        "provider": provider,
    }


@router.get("/auto")
async def lookup_auto(
    url: str,
    tmdb_api_key: str | None = None,
    spotify_client_id: str | None = None,
    spotify_client_secret: str | None = None,
) -> dict:
    provider = _detect_provider(url)
    if provider == "youtube":
        return await lookup_youtube(url)
    if provider == "steam":
        return await lookup_steam(url)
    if provider == "spotify":
        return await lookup_spotify(url, spotify_client_id=spotify_client_id, spotify_client_secret=spotify_client_secret)
    if provider in STREAMING_HOST_PATTERNS:
        return await lookup_streaming(url, tmdb_api_key=tmdb_api_key)
    # Book providers (OpenLibrary, Goodreads, Google Books, Amazon book pages)
    if provider in globals().get("BOOK_HOST_PATTERNS", {}):
        return await lookup_book(url)

    raise HTTPException(
        status.HTTP_400_BAD_REQUEST,
        "Unsupported URL. Try YouTube, Steam, Spotify, Netflix, Prime Video, Max, Disney+, Spotify, Stremio, or book links (OpenLibrary/Goodreads/GoogleBooks).",
    )
