import re
from math import ceil

import httpx
from fastapi import APIRouter, HTTPException, status

router = APIRouter(prefix="/lookup", tags=["lookup"])

YOUTUBE_REGEX = re.compile(
    r"(?:youtu\.be/|youtube\.com/(?:watch\?v=|embed/|shorts/))([A-Za-z0-9_-]{11})"
)


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
            return max(1, ceil(seconds / 60))

    return 0


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
        return max(1, ceil(hours * 60))
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
