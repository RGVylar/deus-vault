import random
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models.content import Content, ContentType
from app.models.user import User
from app.schemas.content import ContentCreate, ContentOut, ContentUpdate, VaultStats

router = APIRouter(prefix="/contents", tags=["contents"])


@router.get("/stats", response_model=VaultStats)
def vault_stats(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> VaultStats:
    """Total pending and consumed minutes + breakdown by type."""
    pending_q = select(
        func.coalesce(func.sum(Content.duration_minutes), 0)
    ).where(Content.user_id == user.id, Content.consumed == False)  # noqa: E712
    consumed_q = select(
        func.coalesce(func.sum(Content.duration_minutes), 0)
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
        select(Content.content_type, func.coalesce(func.sum(Content.duration_minutes), 0))
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


@router.get("", response_model=list[ContentOut])
def list_contents(
    consumed: bool | None = Query(None),
    content_type: ContentType | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Content]:
    q = select(Content).where(Content.user_id == user.id)
    if consumed is not None:
        q = q.where(Content.consumed == consumed)
    if content_type is not None:
        q = q.where(Content.content_type == content_type)
    q = q.order_by(Content.created_at.desc())
    return list(db.scalars(q).all())


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
