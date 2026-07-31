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
    DistractionRewind,
    DistractionStats,
    DistractionTickIn,
    GoodDayOut,
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


def _good_minutes(db: Session, user_id: int, start: datetime | None = None) -> int:
    """Minutos de contenido bueno consumido desde `start` (o todo el histórico)."""
    q = select(Content).where(
        Content.user_id == user_id,
        Content.consumed.is_(True),
    )
    if start is not None:
        q = q.where(Content.consumed_at >= start)
    return sum(_effective_duration(c) for c in db.scalars(q).all())


@router.get("/rewind", response_model=DistractionRewind)
def rewind(
    year: int | None = Query(default=None),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DistractionRewind:
    """Lo perdido durante un año, para la imagen de compartir y la vista anual."""
    if year is None:
        year = date.today().year
    start, end = date(year, 1, 1), date(year, 12, 31)

    rows = db.scalars(
        select(DistractionLog).where(
            DistractionLog.user_id == current_user.id,
            DistractionLog.date >= start,
            DistractionLog.date <= end,
        )
    ).all()

    by_platform: dict[str, PlatformTotal] = {}
    by_month = [0] * 12
    per_day: dict[date, int] = {}
    for r in rows:
        agg = by_platform.setdefault(
            r.platform, PlatformTotal(platform=r.platform, seconds=0, items_count=0)
        )
        agg.seconds += r.seconds
        agg.items_count += r.items_count
        by_month[r.date.month - 1] += r.seconds
        per_day[r.date] = per_day.get(r.date, 0) + r.seconds

    worst_day = max(per_day, key=lambda d: per_day[d]) if per_day else None

    good = db.scalars(
        select(Content).where(
            Content.user_id == current_user.id,
            Content.consumed.is_(True),
            Content.consumed_at >= datetime(year, 1, 1, tzinfo=timezone.utc),
            Content.consumed_at < datetime(year + 1, 1, 1, tzinfo=timezone.utc),
        )
    ).all()

    return DistractionRewind(
        year=year,
        total_seconds=sum(r.seconds for r in rows),
        total_items=sum(r.items_count for r in rows),
        platforms=sorted(by_platform.values(), key=lambda p: p.seconds, reverse=True),
        by_month=by_month,
        worst_day=worst_day,
        worst_day_seconds=per_day.get(worst_day, 0) if worst_day else 0,
        days_with_distraction=len(per_day),
        good_minutes=sum(_effective_duration(c) for c in good),
    )


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

    # Contenido bueno por día (últimos `days` días) para gráficas comparativas
    good_items = db.scalars(
        select(Content).where(
            Content.user_id == current_user.id,
            Content.consumed.is_(True),
            Content.consumed_at >= _utc(series_start),
        )
    ).all()
    good_by_day: dict[date, int] = {}
    for c in good_items:
        if c.consumed_at:
            d = c.consumed_at.date()
            good_by_day[d] = good_by_day.get(d, 0) + _effective_duration(c)
    good_days = [
        GoodDayOut(date=d, minutes=m) for d, m in sorted(good_by_day.items())
    ]

    return DistractionStats(
        today_seconds=today_s,
        week_seconds=week_s,
        month_seconds=month_s,
        total_seconds=total_s,
        total_items=total_items,
        platforms=platforms,
        days=[DistractionDayOut.model_validate(r) for r in day_rows],
        good_days=good_days,
        good_today_minutes=_good_minutes(db, current_user.id, _utc(today)),
        good_week_minutes=_good_minutes(db, current_user.id, _utc(week_start)),
        good_month_minutes=_good_minutes(db, current_user.id, _utc(month_start)),
        good_total_minutes=_good_minutes(db, current_user.id),
    )
