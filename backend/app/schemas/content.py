from datetime import datetime

from pydantic import BaseModel

from app.models.content import ContentType


class ContentCreate(BaseModel):
    title: str
    content_type: ContentType
    url: str | None = None
    thumbnail: str | None = None
    duration_minutes: int = 0
    page_count: int | None = None
    words_per_page: int | None = None
    source_id: str | None = None
    author: str | None = None
    notes: str | None = None


class ContentUpdate(BaseModel):
    title: str | None = None
    url: str | None = None
    thumbnail: str | None = None
    duration_minutes: int | None = None
    page_count: int | None = None
    words_per_page: int | None = None
    author: str | None = None
    notes: str | None = None


class ContentOut(BaseModel):
    id: int
    title: str
    content_type: ContentType
    url: str | None
    thumbnail: str | None
    duration_minutes: int
    page_count: int | None
    words_per_page: int | None
    consumed: bool
    consumed_at: datetime | None
    created_at: datetime
    source_id: str | None
    author: str | None
    notes: str | None

    model_config = {"from_attributes": True}


class VaultStats(BaseModel):
    total_pending_minutes: int
    total_consumed_minutes: int
    pending_count: int
    consumed_count: int
    by_type: dict[str, int]  # pending minutes per type
