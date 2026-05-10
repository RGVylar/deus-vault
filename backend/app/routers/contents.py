import asyncio
import logging
import random
from datetime import date, datetime, timedelta, timezone

import httpx

logger = logging.getLogger(__name__)
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models.content import Content, ContentType
from app.models.user import User
from app.schemas.content import (
    ContentCreate,
    ContentOut,
    ContentUpdate,
    DayStats,
    MonthStats,
    PaginatedContents,
    RewindStats,
    StreamingPlatform,
    TopAuthor,
    TopItem,
    TypeRewindStats,
    VaultStats,
)

router = APIRouter(prefix="/contents", tags=["contents"])

PAGE_LIMIT = 20


def _is_leap_year(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def _effective_duration(c: Content) -> int:
    """Total duration in minutes (series = per-ep * episodes)."""
    if c.content_type == ContentType.series and c.episode_count and c.episode_count > 0:
        return c.duration_minutes * c.episode_count
    return c.duration_minutes


def _remaining_minutes(c: Content) -> int:
    """Minutes left accounting for progress. Used for the pending debt."""
    progress = c.progress or 0

    if c.content_type == ContentType.series:
        total_eps = c.episode_count or 0
        if total_eps > 0:
            eps_done = min(progress, total_eps)
            return max(0, (total_eps - eps_done) * c.duration_minutes)
        return c.duration_minutes  # no episode count → use per-ep duration

    total = c.duration_minutes
    if progress <= 0:
        return total

    if c.content_type == ContentType.book and c.page_count and c.page_count > 0:
        pages_left = max(0, c.page_count - progress)
        return max(0, round(total * pages_left / c.page_count))

    if c.content_type == ContentType.game:
        pct_left = max(0, 100 - progress)
        return max(0, round(total * pct_left / 100))

    # movie, youtube, music: progress = minutes already watched/listened
    return max(0, total - progress)


@router.get("/stats", response_model=VaultStats)
def vault_stats(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> VaultStats:
    """Pending debt (progress-aware) and consumed totals."""
    pending_items = list(
        db.scalars(
            select(Content).where(
                Content.user_id == user.id,
                Content.consumed == False,  # noqa: E712
                Content.abandoned == False,  # noqa: E712
            )
        ).all()
    )
    consumed_items = list(
        db.scalars(
            select(Content).where(Content.user_id == user.id, Content.consumed == True)  # noqa: E712
        ).all()
    )
    abandoned_items = list(
        db.scalars(
            select(Content).where(Content.user_id == user.id, Content.abandoned == True)  # noqa: E712
        ).all()
    )

    total_pending = sum(_remaining_minutes(c) for c in pending_items)
    total_consumed = sum(_effective_duration(c) for c in consumed_items)

    by_type: dict[str, int] = {}
    for c in pending_items:
        key = c.content_type.value
        by_type[key] = by_type.get(key, 0) + _remaining_minutes(c)

    return VaultStats(
        total_pending_minutes=total_pending,
        total_consumed_minutes=total_consumed,
        pending_count=len(pending_items),
        consumed_count=len(consumed_items),
        abandoned_count=len(abandoned_items),
        by_type={k: v for k, v in by_type.items() if v > 0},
    )


@router.get("/rewind", response_model=RewindStats)
def rewind(
    year: int | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RewindStats:
    """Yearly wrap-up: consumed items, calendar heatmap, and time breakdown."""
    if year is None:
        year = datetime.now(timezone.utc).year

    start = datetime(year, 1, 1, tzinfo=timezone.utc)
    end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)

    items = list(
        db.scalars(
            select(Content)
            .where(
                Content.user_id == user.id,
                Content.consumed == True,  # noqa: E712
                Content.consumed_at >= start,
                Content.consumed_at < end,
            )
            .order_by(Content.consumed_at.desc())
        ).all()
    )

    total_minutes = sum(_effective_duration(c) for c in items)
    minutes_in_year = (366 if _is_leap_year(year) else 365) * 24 * 60

    by_type: dict[str, TypeRewindStats] = {}
    for ct in ContentType:
        type_items = [c for c in items if c.content_type == ct]
        if type_items:
            type_minutes = sum(_effective_duration(c) for c in type_items)
            by_type[ct.value] = TypeRewindStats(
                count=len(type_items),
                minutes=type_minutes,
                percentage_of_year=round(type_minutes / minutes_in_year * 100, 3),
            )

    by_month: list[MonthStats] = []
    for m in range(1, 13):
        month_items = [c for c in items if c.consumed_at and c.consumed_at.month == m]
        by_month.append(
            MonthStats(
                month=m,
                count=len(month_items),
                minutes=sum(_effective_duration(c) for c in month_items),
            )
        )

    calendar: dict[str, DayStats] = {}
    for c in items:
        if c.consumed_at:
            day_key = c.consumed_at.strftime("%Y-%m-%d")
            prev = calendar.get(day_key, DayStats(count=0, minutes=0))
            calendar[day_key] = DayStats(
                count=prev.count + 1,
                minutes=prev.minutes + _effective_duration(c),
            )

    # --- Enhanced stats ---

    # Streaks: consecutive days with at least one item consumed
    consumed_dates: set[date] = set()
    for c in items:
        if c.consumed_at:
            consumed_dates.add(c.consumed_at.date())

    streak_max = 0
    streak_current = 0
    if consumed_dates:
        sorted_dates = sorted(consumed_dates)
        cur_streak = 1
        max_streak = 1
        for i in range(1, len(sorted_dates)):
            if (sorted_dates[i] - sorted_dates[i - 1]).days == 1:
                cur_streak += 1
                max_streak = max(max_streak, cur_streak)
            else:
                cur_streak = 1
        streak_max = max_streak

        # Current streak: walk back from today
        today = datetime.now(timezone.utc).date()
        check = today
        streak_current = 0
        while check in consumed_dates:
            streak_current += 1
            check -= timedelta(days=1)

    # Best month: month with most items
    best_month: int | None = None
    if items:
        month_counts = [ms.count for ms in by_month]
        max_count = max(month_counts)
        if max_count > 0:
            best_month = month_counts.index(max_count) + 1  # 1-indexed

    # Avg days to consume: mean of (consumed_at - created_at) in days
    avg_days_to_consume: float | None = None
    deltas = []
    for c in items:
        if c.consumed_at and c.created_at:
            delta = (c.consumed_at - c.created_at).total_seconds() / 86400
            if delta >= 0:
                deltas.append(delta)
    if deltas:
        avg_days_to_consume = round(sum(deltas) / len(deltas), 1)

    # Favorite type: type with most consumed items this year
    favorite_type: str | None = None
    if by_type:
        favorite_type = max(by_type, key=lambda k: by_type[k].count)

    # --- Abandoned stats for this year ---
    abandoned_items_year = list(
        db.scalars(
            select(Content)
            .where(
                Content.user_id == user.id,
                Content.abandoned == True,  # noqa: E712
                Content.abandoned_at >= start,
                Content.abandoned_at < end,
            )
        ).all()
    )
    abandoned_count = len(abandoned_items_year)
    abandoned_minutes = sum(_effective_duration(c) for c in abandoned_items_year)

    most_abandoned_type: str | None = None
    if abandoned_items_year:
        type_counts: dict[str, int] = {}
        for c in abandoned_items_year:
            key = c.content_type.value
            type_counts[key] = type_counts.get(key, 0) + 1
        most_abandoned_type = max(type_counts, key=lambda k: type_counts[k])

    total_finished = len(items) + abandoned_count
    completion_rate: float | None = None
    if total_finished > 0:
        completion_rate = round(len(items) / total_finished * 100, 1)

    # --- Deep stats ---

    # Top YouTube channels (by author, minutes watched)
    yt_authors: dict[str, dict] = {}
    for c in items:
        if c.content_type == ContentType.youtube and c.author:
            key = c.author.strip()
            if key not in yt_authors:
                yt_authors[key] = {"name": key, "count": 0, "minutes": 0, "thumbnail": None}
            yt_authors[key]["count"] += 1
            yt_authors[key]["minutes"] += _effective_duration(c)
            # Keep the first channel_thumbnail we find for this author
            if not yt_authors[key]["thumbnail"] and c.channel_thumbnail:
                yt_authors[key]["thumbnail"] = c.channel_thumbnail
    top_youtube_channels = [
        TopAuthor(**v)
        for v in sorted(yt_authors.values(), key=lambda x: x["minutes"], reverse=True)[:5]
    ]

    # Top 3 items per content type (by effective duration)
    top_items_by_type: dict[str, list[TopItem]] = {}
    for ct in ContentType:
        type_items = [c for c in items if c.content_type == ct]
        if type_items:
            sorted_items = sorted(type_items, key=_effective_duration, reverse=True)[:3]
            top_items_by_type[ct.value] = [
                TopItem(
                    id=c.id,
                    title=c.title,
                    author=c.author,
                    thumbnail=c.thumbnail,
                    minutes=_effective_duration(c),
                )
                for c in sorted_items
            ]

    # Streaming platform breakdown for movies + series
    PLATFORM_NAMES = {"netflix", "prime video", "max", "disney+", "crunchyroll", "stremio", "hbo", "apple tv+", "paramount+", "peacock", "hulu"}
    platform_data: dict[str, dict] = {}
    for c in items:
        if c.content_type in (ContentType.movie, ContentType.series) and c.author:
            plat = c.author.strip()
            plat_lower = plat.lower()
            # Only count known platforms, not random author names
            if any(p in plat_lower for p in PLATFORM_NAMES):
                if plat not in platform_data:
                    platform_data[plat] = {"name": plat, "count": 0, "minutes": 0}
                platform_data[plat]["count"] += 1
                platform_data[plat]["minutes"] += _effective_duration(c)
    streaming_breakdown = [
        StreamingPlatform(**v)
        for v in sorted(platform_data.values(), key=lambda x: x["minutes"], reverse=True)
    ]

    # Top book authors
    book_authors: dict[str, dict] = {}
    for c in items:
        if c.content_type == ContentType.book and c.author:
            key = c.author.strip()
            if key not in book_authors:
                book_authors[key] = {"name": key, "count": 0, "minutes": 0}
            book_authors[key]["count"] += 1
            book_authors[key]["minutes"] += _effective_duration(c)
    top_book_authors = [
        TopAuthor(**v)
        for v in sorted(book_authors.values(), key=lambda x: x["minutes"], reverse=True)[:5]
    ]

    return RewindStats(
        year=year,
        total_consumed_minutes=total_minutes,
        total_consumed_count=len(items),
        percentage_of_year=round(total_minutes / minutes_in_year * 100, 3),
        by_type=by_type,
        by_month=by_month,
        calendar=calendar,
        items=[ContentOut.model_validate(c) for c in items],
        streak_max=streak_max,
        streak_current=streak_current,
        best_month=best_month,
        avg_days_to_consume=avg_days_to_consume,
        favorite_type=favorite_type,
        abandoned_count=abandoned_count,
        abandoned_minutes=abandoned_minutes,
        most_abandoned_type=most_abandoned_type,
        completion_rate=completion_rate,
        top_youtube_channels=top_youtube_channels,
        top_items_by_type=top_items_by_type,
        streaming_breakdown=streaming_breakdown,
        top_book_authors=top_book_authors,
    )


@router.get("/collections", response_model=list[str])
def list_collections(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[str]:
    """Return distinct non-null collection names for the user, alphabetically."""
    rows = db.scalars(
        select(Content.collection)
        .where(Content.user_id == user.id, Content.collection.isnot(None))
        .distinct()
        .order_by(Content.collection.asc())
    ).all()
    return [r for r in rows if r]


# Maps author label → provider key for content added before the provider field existed
_AUTHOR_TO_PROVIDER: dict[str, str] = {
    "Netflix": "netflix",
    "Prime Video": "prime",
    "Max": "max",
    "Disney+": "disney",
    "Crunchyroll": "crunchyroll",
    "Stremio": "stremio",
    "Apple TV+": "appletv",
}
_PROVIDER_TO_AUTHOR: dict[str, str] = {v: k for k, v in _AUTHOR_TO_PROVIDER.items()}


@router.get("/providers", response_model=list[str])
def list_providers(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[str]:
    """Return distinct providers for the user's pending content (from provider field or known authors)."""
    base = (
        select(Content)
        .where(Content.user_id == user.id, Content.consumed == False, Content.abandoned == False)  # noqa: E712
    )
    items = db.scalars(base).all()
    found: set[str] = set()
    for item in items:
        if item.provider:
            found.add(item.provider)
        elif item.author and item.author in _AUTHOR_TO_PROVIDER:
            found.add(_AUTHOR_TO_PROVIDER[item.author])
    return sorted(found)


@router.get("/check-duplicate", response_model=ContentOut | None)
def check_duplicate(
    source_id: str | None = Query(None),
    url: str | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Content | None:
    """Return the first matching pending/consumed item for this user by source_id or url."""
    if not source_id and not url:
        return None
    q = select(Content).where(Content.user_id == user.id)
    if source_id:
        q = q.where(Content.source_id == source_id)
    else:
        q = q.where(Content.url == url)
    return db.scalars(q.limit(1)).first()


@router.get("", response_model=PaginatedContents)
def list_contents(
    consumed: bool | None = Query(None),
    abandoned: bool | None = Query(None),
    content_type: ContentType | None = Query(None),
    collection: str | None = Query(None, max_length=100),
    provider: str | None = Query(None, max_length=50),
    search: str | None = Query(None, max_length=200),
    sort: str = Query(default="recent", pattern="^(recent|duration_asc|duration_desc|title_asc|rating_desc|rating_asc)$"),
    limit: int = Query(default=PAGE_LIMIT, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PaginatedContents:
    q = select(Content).where(Content.user_id == user.id)
    if abandoned is not None:
        q = q.where(Content.abandoned == abandoned)
        if abandoned is False:
            # when fetching non-abandoned, also exclude abandoned items
            pass
    if consumed is not None:
        q = q.where(Content.consumed == consumed)
        # When fetching pending (consumed=False), exclude abandoned by default
        if consumed is False and abandoned is None:
            q = q.where(Content.abandoned == False)  # noqa: E712
    if content_type is not None:
        q = q.where(Content.content_type == content_type)
    if collection is not None:
        q = q.where(Content.collection == collection)
    if provider is not None:
        author_label = _PROVIDER_TO_AUTHOR.get(provider)
        if author_label:
            q = q.where(or_(Content.provider == provider, Content.author == author_label))
        else:
            q = q.where(Content.provider == provider)
    if search and search.strip():
        term = f"%{search.strip().lower()}%"
        q = q.where(
            or_(
                func.lower(Content.title).like(term),
                func.lower(Content.author).like(term),
            )
        )

    # Pinned items always surface first (for pending vault)
    if sort == "duration_asc":
        q = q.order_by(Content.pinned.desc(), Content.duration_minutes.asc(), Content.created_at.desc())
    elif sort == "duration_desc":
        q = q.order_by(Content.pinned.desc(), Content.duration_minutes.desc(), Content.created_at.desc())
    elif sort == "title_asc":
        q = q.order_by(Content.pinned.desc(), func.lower(Content.title).asc())
    elif sort == "rating_desc":
        q = q.order_by(Content.pinned.desc(), Content.rating.desc().nulls_last(), Content.created_at.desc())
    elif sort == "rating_asc":
        q = q.order_by(Content.pinned.desc(), Content.rating.asc().nulls_last(), Content.created_at.desc())
    else:  # recent
        q = q.order_by(Content.pinned.desc(), Content.created_at.desc())

    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    items = list(db.scalars(q.limit(limit).offset(offset)).all())

    return PaginatedContents(items=items, total=total, offset=offset, limit=limit)


@router.post("", response_model=ContentOut, status_code=status.HTTP_201_CREATED)
def create_content(
    payload: ContentCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Content:
    content = Content(user_id=user.id, **payload.model_dump())
    db.add(content)
    db.commit()
    db.refresh(content)
    return content


@router.patch("/{content_id}", response_model=ContentOut)
def update_content(
    content_id: int,
    payload: ContentUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Content:
    content = db.get(Content, content_id)
    if not content or content.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Content not found")
    for key, val in payload.model_dump(exclude_unset=True).items():
        setattr(content, key, val)
    db.commit()
    db.refresh(content)
    return content


@router.post("/{content_id}/consume", response_model=ContentOut)
def mark_consumed(
    content_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Content:
    content = db.get(Content, content_id)
    if not content or content.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Content not found")
    if content.consumed:
        # Already consumed — increment the counter and update the timestamp
        content.times_consumed = (content.times_consumed or 1) + 1
    else:
        content.consumed = True
        content.times_consumed = 1
    content.consumed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(content)
    return content


@router.post("/{content_id}/abandon", response_model=ContentOut)
def mark_abandoned(
    content_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Content:
    content = db.get(Content, content_id)
    if not content or content.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Content not found")
    content.abandoned = True
    content.abandoned_at = datetime.now(timezone.utc)
    content.consumed = False
    content.consumed_at = None
    db.commit()
    db.refresh(content)
    return content


@router.post("/{content_id}/restore", response_model=ContentOut)
def restore_content(
    content_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Content:
    """Restore an abandoned (or consumed) item back to pending."""
    content = db.get(Content, content_id)
    if not content or content.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Content not found")
    content.abandoned = False
    content.abandoned_at = None
    content.consumed = False
    content.consumed_at = None
    db.commit()
    db.refresh(content)
    return content


@router.post("/{content_id}/unconsume", response_model=ContentOut)
def mark_unconsumed(
    content_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Content:
    content = db.get(Content, content_id)
    if not content or content.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Content not found")
    content.consumed = False
    content.consumed_at = None
    content.times_consumed = 0
    db.commit()
    db.refresh(content)
    return content


@router.delete("/{content_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_content(
    content_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    content = db.get(Content, content_id)
    if not content or content.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Content not found")
    db.delete(content)
    db.commit()


@router.get("/random", response_model=ContentOut)
def random_pick(
    content_type: ContentType | None = Query(None),
    min_duration: int | None = Query(None, ge=0, description="Min remaining minutes"),
    max_duration: int | None = Query(None, ge=0, description="Max remaining minutes"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Content:
    """Pick a random pending content item, optionally filtered by available time.
    Pinned items have double weight."""
    q = select(Content).where(
        Content.user_id == user.id,
        Content.consumed == False,  # noqa: E712
        Content.abandoned == False,  # noqa: E712
    )
    if content_type is not None:
        q = q.where(Content.content_type == content_type)
    items = list(db.scalars(q).all())

    if min_duration is not None or max_duration is not None:
        def fits(c: Content) -> bool:
            remaining = _remaining_minutes(c)
            if min_duration is not None and remaining < min_duration:
                return False
            if max_duration is not None and remaining > max_duration:
                return False
            return True
        items = [c for c in items if fits(c)]

    if not items:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No pending content in that time range")

    # Pinned items appear twice in the pool for double weight
    pool = []
    for c in items:
        pool.append(c)
        if c.pinned:
            pool.append(c)

    return random.choice(pool)


@router.post("/backfill-channel-thumbnails")
async def backfill_channel_thumbnails(
    force: bool = Query(False, description="Re-fetch even items that already have a thumbnail"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Re-fetch YouTube channel thumbnails for items that are missing one.

    Pass ?force=true to also overwrite existing (potentially wrong) thumbnails.
    Safe to call multiple times — without force, only touches NULL rows.
    Returns counts of how many were updated vs failed.
    """
    from app.routers.lookup import _extract_channel_thumbnail

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Cookie": "CONSENT=YES+cb.20210328-17-p0.en+FX+119",
    }

    # Find YouTube items to process
    q = select(Content).where(
        Content.user_id == user.id,
        Content.content_type == "youtube",
        Content.source_id.isnot(None),
    )
    if not force:
        q = q.where(Content.channel_thumbnail.is_(None))
    items = list(db.scalars(q).all())

    if not items:
        logger.info("backfill: no YouTube items missing channel thumbnails for user %s", user.id)
        return {"updated": 0, "failed": 0, "total": 0}

    logger.info("backfill: found %d YouTube items without channel thumbnail for user %s", len(items), user.id)

    updated = 0
    failed = 0

    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=15) as client:
        for item in items:
            watch_url = f"https://www.youtube.com/watch?v={item.source_id}"
            try:
                resp = await client.get(watch_url)
                thumb = _extract_channel_thumbnail(resp.text)
                if thumb:
                    item.channel_thumbnail = thumb
                    updated += 1
                    logger.info("backfill: [OK]  %s — %s", item.source_id, item.title[:50])
                else:
                    failed += 1
                    logger.warning("backfill: [MISS] %s — %s (no thumbnail in page)", item.source_id, item.title[:50])
            except Exception as exc:
                failed += 1
                logger.warning("backfill: [ERR]  %s — %s: %s", item.source_id, item.title[:50], exc)
            # Small delay to be polite to YouTube
            await asyncio.sleep(0.5)

    db.commit()
    logger.info("backfill: done — updated=%d failed=%d total=%d", updated, failed, len(items))
    return {"updated": updated, "failed": failed, "total": len(items)}
