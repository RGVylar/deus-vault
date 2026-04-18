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
    episode_count: int | None = None
    seasons: int | None = None
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
    episode_count: int | None = None
    seasons: int | None = None
    author: str | None = None
    notes: str | None = None
    progress: int | None = None


class ContentOut(BaseModel):
    id: int
    title: str
    content_type: ContentType
    url: str | None
    thumbnail: str | None
    duration_minutes: int
    page_count: int | None
    words_per_page: int | None
    episode_count: int | None
    seasons: int | None
    consumed: bool
    consumed_at: datetime | None
    created_at: datetime
    source_id: str | None
    author: str | None
    notes: str | None
    progress: int | None

    model_config = {"from_attributes": True}


class VaultStats(BaseModel):
    total_pending_minutes: int
    total_consumed_minutes: int
    pending_count: int
    consumed_count: int
    by_type: dict[str, int]  # pending minutes per type


class PaginatedContents(BaseModel):
    items: list[ContentOut]
    total: int
    offset: int
    limit: int


class TypeRewindStats(BaseModel):
    count: int
    minutes: int
    percentage_of_year: float


class MonthStats(BaseModel):
    month: int
    count: int
    minutes: int


class DayStats(BaseModel):
    count: int
    minutes: int


class RewindStats(BaseModel):
    year: int
    total_consumed_minutes: int
    total_consumed_count: int
    percentage_of_year: float
    by_type: dict[str, TypeRewindStats]
    by_month: list[MonthStats]
    calendar: dict[str, DayStats]  # "YYYY-MM-DD" -> DayStats
    items: list[ContentOut]
