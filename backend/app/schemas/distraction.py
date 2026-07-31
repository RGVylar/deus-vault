from datetime import date

from pydantic import BaseModel, Field

VALID_PLATFORMS = {"shorts", "tiktok", "twitter", "reels"}


class DistractionEntry(BaseModel):
    date: date
    platform: str
    seconds: int = Field(ge=0, le=86400)
    items_count: int = Field(default=0, ge=0)


class DistractionTickIn(BaseModel):
    entries: list[DistractionEntry]


class PlatformTotal(BaseModel):
    platform: str
    seconds: int
    items_count: int


class DistractionDayOut(BaseModel):
    date: date
    platform: str
    seconds: int
    items_count: int

    model_config = {"from_attributes": True}


class GoodDayOut(BaseModel):
    date: date
    minutes: int


class DistractionRewind(BaseModel):
    """Lo perdido en un año concreto. `stats` solo sabe de 7 días, 30 y el
    histórico completo, así que el Rewind necesitaba su propio corte."""

    year: int
    total_seconds: int
    total_items: int
    platforms: list[PlatformTotal]
    by_month: list[int]              # 12 posiciones, segundos
    worst_day: date | None
    worst_day_seconds: int
    days_with_distraction: int
    good_minutes: int                # contenido consumido ese año, para comparar


class DistractionStats(BaseModel):
    # Tiempo perdido (segundos)
    today_seconds: int
    week_seconds: int      # últimos 7 días
    month_seconds: int     # últimos 30 días
    total_seconds: int
    total_items: int
    # Desglose por plataforma (todo el histórico)
    platforms: list[PlatformTotal]
    # Serie diaria para gráficas (últimos N días)
    days: list[DistractionDayOut]
    # Minutos de contenido bueno consumido por día (últimos N días)
    good_days: list[GoodDayOut]
    # Tiempo bueno (minutos de contenido consumido) para comparar
    good_today_minutes: int
    good_week_minutes: int
    good_month_minutes: int
    good_total_minutes: int
