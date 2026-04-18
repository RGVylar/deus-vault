import random
from datetime import datetime, timezone

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
            select(Content).where(Content.user_id == user.id, Content.consumed == False)  # noqa: E712
        ).all()
    )
    consumed_items = list(
        db.scalars(
            select(Content).where(Content.user_id == user.id, Content.consumed == True)  # noqa: E712
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

    return RewindStats(
        year=year,
        total_consumed_minutes=total_minutes,
        total_consumed_count=len(items),
        percentage_of_year=round(total_minutes / minutes_in_year * 100, 3),
        by_type=by_type,
        by_month=by_month,
        calendar=calendar,
        items=[ContentOut.model_validate(c) for c in items],
    )


@router.get("", response_model=PaginatedContents)
def list_contents(
    consumed: bool | None = Query(None),
    content_type: ContentType | None = Query(None),
    search: str | None = Query(None, max_length=200),
    limit: int = Query(default=PAGE_LIMIT, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PaginatedContents:
    q = select(Content).where(Content.user_id == user.id)
    if consumed is not None:
        q = q.where(Content.consumed == consumed)
    if content_type is not None:
        q = q.where(Content.content_type == content_type)
    if search and search.strip():
        term = f"%{search.strip().lower()}%"
        q = q.where(
            or_(
                func.lower(Content.title).like(term),
                func.lower(Content.author).like(term),
            )
        )

    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    items = list(
        db.scalars(q.order_by(Content.created_at.desc()).limit(limit).offset(offset)).all()
    )

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
    content.consumed = True
    content.consumed_at = datetime.now(timezone.utc)
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
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Content:
    """Pick a random pending content item."""
    q = select(Content).where(Content.user_id == user.id, Content.consumed == False)  # noqa: E712
    if content_type is not None:
        q = q.where(Content.content_type == content_type)
    items = list(db.scalars(q).all())
    if not items:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No pending content")
    return random.choice(items)
