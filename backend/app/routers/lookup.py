import re

import httpx
from fastapi import APIRouter, HTTPException, status

router = APIRouter(prefix="/lookup", tags=["lookup"])

YOUTUBE_REGEX = re.compile(
    r"(?:youtu\.be/|youtube\.com/(?:watch\?v=|embed/|shorts/))([A-Za-z0-9_-]{11})"
)


@router.get("/youtube")
async def lookup_youtube(url: str) -> dict:
    """Use YouTube oEmbed to get title, author, thumbnail. Duration from page."""
    match = YOUTUBE_REGEX.search(url)
    if not match:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid YouTube URL")
    video_id = match.group(1)
    oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(oembed_url)
    if resp.status_code != 200:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Video not found")
    data = resp.json()
    return {
        "title": data.get("title", ""),
        "author": data.get("author_name", ""),
        "thumbnail": f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
        "source_id": video_id,
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "duration_minutes": 0,  # oEmbed doesn't give duration — user can edit
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
    return {
        "title": info.get("name", ""),
        "author": ", ".join(info.get("developers", [])),
        "thumbnail": info.get("header_image", ""),
        "source_id": app_id,
        "url": f"https://store.steampowered.com/app/{app_id}",
        "duration_minutes": 0,  # Steam doesn't provide HLTB — user can edit
    }
