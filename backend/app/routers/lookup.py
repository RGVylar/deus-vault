import re
import json
import sys
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
}

PROVIDER_LABELS: dict[str, str] = {
    "netflix": "Netflix",
    "prime": "Prime Video",
    "max": "Max",
    "disney": "Disney+",
    "stremio": "Stremio",
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

    if "youtube.com" in host or "youtu.be" in host:
        return "youtube"
    if "store.steampowered.com" in host:
        return "steam"
    return None


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
    cleaned = re.sub(r"\s*[|\-–—]\s*(Watch|Streaming|Official Site).*$", "", cleaned, flags=re.IGNORECASE)
    # Common streaming CTA prefixes that hurt TMDb matching.
    cleaned = re.sub(r"^(watch|ver|voir|guarda|regarder|assistir)\s+", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


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


async def _tmdb_fallback(query: str) -> dict:
    if not settings.tmdb_api_key or not query:
        print(f"[TMDB] No key or query: key={bool(settings.tmdb_api_key)}, query={query}", file=sys.stderr)
        return {}

    query = query.strip()
    alt_query = re.sub(r"^(watch|ver|voir|guarda|regarder|assistir)\s+", "", query, flags=re.IGNORECASE).strip()
    print(f"[TMDB] Searching: query='{query}' | alt='{alt_query}'", file=sys.stderr)

    params = {
        "api_key": settings.tmdb_api_key,
        "query": query,
        "language": "en-US",
        "include_adult": "false",
    }

    async with httpx.AsyncClient(timeout=10) as client:
        search_resp = await client.get("https://api.themoviedb.org/3/search/multi", params=params)
        if search_resp.status_code != 200:
            print(f"[TMDB] First search failed: {search_resp.status_code}", file=sys.stderr)
            return {}

        results = search_resp.json().get("results", [])
        print(f"[TMDB] First search: {len(results)} results", file=sys.stderr)
        if not results and alt_query and alt_query.lower() != query.lower():
            print(f"[TMDB] Retrying with: '{alt_query}'", file=sys.stderr)
            retry_resp = await client.get(
                "https://api.themoviedb.org/3/search/multi",
                params={**params, "query": alt_query},
            )
            if retry_resp.status_code == 200:
                results = retry_resp.json().get("results", [])
                print(f"[TMDB] Retry: {len(results)} results", file=sys.stderr)

        selected = next((r for r in results if r.get("media_type") in {"movie", "tv"}), None)
        if not selected:
            print(f"[TMDB] No movie/tv selected from {len(results)} results", file=sys.stderr)
            if results:
                print(f"[TMDB] Sample result: {results[0]}", file=sys.stderr)
            return {}

        media_type = selected.get("media_type")
        item_id = selected.get("id")
        details_resp = await client.get(
            f"https://api.themoviedb.org/3/{media_type}/{item_id}",
            params={"api_key": settings.tmdb_api_key, "language": "en-US"},
        )
        details = details_resp.json() if details_resp.status_code == 200 else {}

    runtime = 0
    if media_type == "movie":
        runtime = int(details.get("runtime") or 0)
    else:
        episodes_runtime = details.get("episode_run_time") or []
        runtime = int(episodes_runtime[0]) if episodes_runtime else 0

    title = selected.get("title") or selected.get("name") or query
    poster_path = selected.get("poster_path") or details.get("poster_path")
    thumbnail = f"https://image.tmdb.org/t/p/w780{poster_path}" if poster_path else ""

    return {
        "title": title,
        "duration_minutes": runtime,
        "thumbnail": thumbnail,
        "source_id": f"tmdb:{media_type}:{item_id}",
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

    tmdb = await _tmdb_fallback(title)
    if tmdb:
        if not title:
            title = tmdb.get("title", "")
        tmdb_duration = int(tmdb.get("duration_minutes") or 0)
        # Replace suspiciously short scraped durations with TMDb runtime when available.
        if tmdb_duration > 0 and (duration_minutes <= 0 or duration_minutes < 15):
            duration_minutes = tmdb_duration
        if not thumbnail:
            thumbnail = tmdb.get("thumbnail", "")

    source_id = _extract_source_id(url, provider) or tmdb.get("source_id", "") if tmdb else _extract_source_id(url, provider)

    return {
        "title": title,
        "author": PROVIDER_LABELS.get(provider, ""),
        "thumbnail": thumbnail,
        "source_id": source_id,
        "url": url,
        "duration_minutes": duration_minutes,
        "suggested_content_type": "movie",
        "provider": provider,
    }


@router.get("/auto")
async def lookup_auto(url: str) -> dict:
    provider = _detect_provider(url)
    if provider == "youtube":
        return await lookup_youtube(url)
    if provider == "steam":
        return await lookup_steam(url)
    if provider in STREAMING_HOST_PATTERNS:
        return await lookup_streaming(url)

    raise HTTPException(
        status.HTTP_400_BAD_REQUEST,
        "Unsupported URL. Try YouTube, Steam, Netflix, Prime Video, Max, Disney+, or Stremio.",
    )
