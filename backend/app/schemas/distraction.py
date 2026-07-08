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
    # Tiempo bueno (minutos de contenido consumido) para comparar
    good_today_minutes: int
    good_week_minutes: int
    good_month_minutes: int
