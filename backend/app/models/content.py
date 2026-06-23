import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ContentType(str, enum.Enum):
    youtube = "youtube"
    movie = "movie"
    series = "series"
    book = "book"
    game = "game"
    music = "music"


class Content(Base):
    __tablename__ = "contents"
    __table_args__ = (
        # Pending vault: the most common query (user + not consumed + not abandoned)
        Index("ix_contents_user_pending", "user_id", "consumed", "abandoned"),
        # Consumed history + rewind (filter by year via consumed_at)
        Index("ix_contents_user_consumed_at", "user_id", "consumed", "consumed_at"),
        # Abandoned stats
        Index("ix_contents_user_abandoned", "user_id", "abandoned"),
        # Type filter on top of user
        Index("ix_contents_user_type", "user_id", "content_type"),
        # Default sort column
        Index("ix_contents_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[ContentType] = mapped_column(Enum(ContentType), nullable=False)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    thumbnail: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Optional book metadata
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    words_per_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Optional series metadata (duration_minutes = per-episode runtime for series)
    episode_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    seasons: Mapped[int | None] = mapped_column(Integer, nullable=True)
    consumed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    abandoned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    abandoned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    times_consumed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_episode_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # Progress tracking (page for books, episode for series, minutes for video, % for games)
    progress: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Organisation
    pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    collection: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Extra metadata
    source_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    author: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    channel_thumbnail: Mapped[str | None] = mapped_column(Text, nullable=True)
    rating: Mapped[float | None] = mapped_column(Float(), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    trailer_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    genres: Mapped[str | None] = mapped_column(String(500), nullable=True)  # comma-separated
    streaming_providers: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON: ["Netflix","Max"]
    imdb_id: Mapped[str | None] = mapped_column(String(20), nullable=True)  # tt1234567

    user: Mapped["User"] = relationship(back_populates="contents")  # noqa: F821
