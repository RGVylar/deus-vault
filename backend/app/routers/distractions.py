from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.content import Content
from app.models.distraction import DistractionLog
from app.routers.auth import get_current_user
from app.routers.contents import _effective_duration
from app.schemas.distraction import (
    VALID_PLATFORMS,
    DistractionDayOut,
    DistractionStats,
    DistractionTickIn,
    PlatformTotal,
)

router = APIRouter(prefix="/distractions", tags=["distractions"])


@router.post("/tick", status_code=204)
def tick(
    body: DistractionTickIn,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Acumula segundos perdidos. Upsert por (usuario, día, plataforma)."""
    today = date.today()
    for entry in body.entries:
        if entry.platform not in VALID_PLATFORMS:
            raise HTTPException(status_code=422, detail=f"Plataforma desconocida: {entry.platform}")
        # No aceptar fechas futuras ni de hace más de una semana (buffer atrasado de la extensión)
        if entry.date > today or entry.date < today - timedelta(days=7):
            continue
        if entry.seconds == 0 and entry.items_count == 0:
            continue

        row = db.scalars(
            select(DistractionLog).where(
                DistractionLog.user_id == current_user.id,
                DistractionLog.date == entry.date,
                DistractionLog.platform == entry.platform,
            )
        ).first()
        if row:
            row.seconds += entry.seconds
            row.items_count += entry.items_count
        else:
            db.add(DistractionLog(
                user_id=current_user.id,
                date=entry.date,
                platform=entry.platform,
                seconds=entry.seconds,
                items_count=entry.items_count,
            ))
    db.commit()


def _good_minutes(db: Session, user_id: int, start: datetime) -> int:
    """Minutos de contenido bueno consumido desde `start`."""
    items = db.scalars(
        select(Content).where(
            Content.user_id == user_id,
            Content.consumed.is_(True),
            Content.consumed_at >= start,
        )
    ).all()
    return sum(_effective_duration(c) for c in items)


@router.get("/stats", response_model=DistractionStats)
def stats(
    days: int = Query(default=30, ge=1, le=365),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    today = date.today()
    week_start = today - timedelta(days=6)
    month_start = today - timedelta(days=29)

    rows = db.scalars(
        select(DistractionLog).where(DistractionLog.user_id == current_user.id)
    ).all()

    today_s = sum(r.seconds for r in rows if r.date == today)
    week_s = sum(r.seconds for r in rows if r.date >= week_start)
    month_s = sum(r.seconds for r in rows if r.date >= month_start)
    total_s = sum(r.seconds for r in rows)
    total_items = sum(r.items_count for r in rows)

    # Desglose por plataforma (histórico completo)
    by_platform: dict[str, PlatformTotal] = {}
    for r in rows:
        agg = by_platform.setdefault(
            r.platform, PlatformTotal(platform=r.platform, seconds=0, items_count=0)
        )
        agg.seconds += r.seconds
        agg.items_count += r.items_count
    platforms = sorted(by_platform.values(), key=lambda p: p.seconds, reverse=True)

    # Serie diaria (últimos `days` días)
    series_start = today - timedelta(days=days - 1)
    day_rows = sorted(
        (r for r in rows if r.date >= series_start),
        key=lambda r: (r.date, r.platform),
    )

    # Tiempo bueno para comparar (consumed_at es UTC)
    def _utc(d: date) -> datetime:
        return datetime.combine(d, time.min, tzinfo=timezone.utc)

    return DistractionStats(
        today_seconds=today_s,
        week_seconds=week_s,
        month_seconds=month_s,
        total_seconds=total_s,
        total_items=total_items,
        platforms=platforms,
        days=[DistractionDayOut.model_validate(r) for r in day_rows],
        good_today_minutes=_good_minutes(db, current_user.id, _utc(today)),
        good_week_minutes=_good_minutes(db, current_user.id, _utc(week_start)),
        good_month_minutes=_good_minutes(db, current_user.id, _utc(month_start)),
    )
