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
    pinned: bool = False
    collection: str | None = None


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
    pinned: bool | None = None
    collection: str | None = None
    consumed_at: datetime | None = None  # allows correcting the consumed date


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
    abandoned: bool
    abandoned_at: datetime | None
    created_at: datetime
    source_id: str | None
    author: str | None
    notes: str | None
    progress: int | None
    pinned: bool
    collection: str | None

    model_config = {"from_attributes": True}


class VaultStats(BaseModel):
    total_pending_minutes: int
    total_consumed_minutes: int
    pending_count: int
    consumed_count: int
    abandoned_count: int
    by_type: dict[str, int]  # pending minutes per type


class PaginatedContents(BaseModel):
    items: list[ContentOut]
    total: int
    offset: int
    limit: int


class TopItem(BaseModel):
    id: int
    title: str
    author: str | None
    thumbnail: str | None
    minutes: int


class TopAuthor(BaseModel):
    name: str
    count: int
    minutes: int


class StreamingPlatform(BaseModel):
    name: str
    count: int
    minutes: int


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
    # Enhanced stats
    streak_max: int
    streak_current: int
    best_month: int | None          # month number (1-12)
    avg_days_to_consume: float | None
    favorite_type: str | None
    # Abandoned stats
    abandoned_count: int
    abandoned_minutes: int
    most_abandoned_type: str | None
    completion_rate: float | None   # consumed / (consumed + abandoned) * 100
    # Deep stats
    top_youtube_channels: list[TopAuthor]      # top channels by watch time
    top_items_by_type: dict[str, list[TopItem]]  # top 3 per type
    streaming_breakdown: list[StreamingPlatform]  # platforms for movies+series
    top_book_authors: list[TopAuthor]           # top book authors
