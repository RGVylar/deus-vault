import random
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case, func, select
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


def _effective_duration(model: type) -> object:
    """SQL expression: series total = duration_minutes * episode_count, else duration_minutes."""
    return case(
        (
            (model.content_type == ContentType.series)
            & model.episode_count.isnot(None)
            & (model.episode_count > 0),
            model.duration_minutes * model.episode_count,
        ),
        else_=model.duration_minutes,
    )


def _is_leap_year(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


@router.get("/stats", response_model=VaultStats)
def vault_stats(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> VaultStats:
    """Total pending and consumed minutes + breakdown by type."""
    pending_q = select(
        func.coalesce(func.sum(_effective_duration(Content)), 0)
    ).where(Content.user_id == user.id, Content.consumed == False)  # noqa: E712
    consumed_q = select(
        func.coalesce(func.sum(_effective_duration(Content)), 0)
    ).where(Content.user_id == user.id, Content.consumed == True)  # noqa: E712

    pending_count_q = select(func.count()).where(
        Content.user_id == user.id, Content.consumed == False  # noqa: E712
    )
    consumed_count_q = select(func.count()).where(
        Content.user_id == user.id, Content.consumed == True  # noqa: E712
    )

    total_pending = db.scalar(pending_q) or 0
    total_consumed = db.scalar(consumed_q) or 0
    pending_count = db.scalar(pending_count_q) or 0
    consumed_count = db.scalar(consumed_count_q) or 0

    # By type (pending only)
    by_type_rows = db.execute(
        select(Content.content_type, func.coalesce(func.sum(_effective_duration(Content)), 0))
        .where(Content.user_id == user.id, Content.consumed == False)  # noqa: E712
        .group_by(Content.content_type)
    ).all()
    by_type = {row[0].value: row[1] for row in by_type_rows}

    return VaultStats(
        total_pending_minutes=total_pending,
        total_consumed_minutes=total_consumed,
        pending_count=pending_count,
        consumed_count=consumed_count,
        by_type=by_type,
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

    def item_duration(c: Content) -> int:
        if c.content_type == ContentType.series and c.episode_count and c.episode_count > 0:
            return c.duration_minutes * c.episode_count
        return c.duration_minutes

    total_minutes = sum(item_duration(c) for c in items)
    minutes_in_year = (366 if _is_leap_year(year) else 365) * 24 * 60

    # By type
    by_type: dict[str, TypeRewindStats] = {}
    for ct in ContentType:
        type_items = [c for c in items if c.content_type == ct]
        if type_items:
            type_minutes = sum(item_duration(c) for c in type_items)
            by_type[ct.value] = TypeRewindStats(
                count=len(type_items),
                minutes=type_minutes,
                percentage_of_year=round(type_minutes / minutes_in_year * 100, 3),
            )

    # By month
    by_month: list[MonthStats] = []
    for m in range(1, 13):
        month_items = [c for c in items if c.consumed_at and c.consumed_at.month == m]
        by_month.append(
            MonthStats(
                month=m,
                count=len(month_items),
                minutes=sum(item_duration(c) for c in month_items),
            )
        )

    # Calendar heatmap
    calendar: dict[str, DayStats] = {}
    for c in items:
        if c.consumed_at:
            day_key = c.consumed_at.strftime("%Y-%m-%d")
            prev = calendar.get(day_key, DayStats(count=0, minutes=0))
            calendar[day_key] = DayStats(
                count=prev.count + 1,
                minutes=prev.minutes + item_duration(c),
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

    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    items = list(db.scalars(q.order_by(Content.created_at.desc()).limit(limit).offset(offset)).all())

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
