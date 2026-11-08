"""Consumption aggregates (G2): computed from `irrigation_applied` on the caller's VISIBLE parcels only (never from the farm
area, never from a shared cache), so a worker's totals are the manual sum of their own parcels."""
import datetime as dt
import uuid
from typing import Any

from sqlalchemy import text

from app.auth.farm_context import FarmContext
from app.domain.consumption import summarise_consumption
from app.irrigation import cache
from app.monitoring.access_sql import VISIBLE_PARCELS_SQL, scope_params

_SQL = (
    "SELECT p.id AS parcel_id, COALESCE(p.area_calc_ha, p.area_declared_ha, ST_Area(p.geometry::geography) / 10000.0) AS area_ha, COALESCE(sum(a.volume_m3), 0) AS volume_m3,"
    " count(a.id) AS events FROM parcels p LEFT JOIN irrigation_applied a ON a.farm_id = p.farm_id AND a.parcel_id = p.id"
    " AND a.performed_on >= :first AND a.performed_on <= :last {season}"
    f" WHERE p.id IN ({VISIBLE_PARCELS_SQL}) GROUP BY p.id, p.area_calc_ha, p.area_declared_ha, p.geometry ORDER BY p.id"
)


def add_months(day: dt.date, months: int) -> dt.date:
    index = day.year * 12 + day.month - 1 + months
    year, month = divmod(index, 12)
    month += 1
    for d in (day.day, 30, 29, 28):
        try:
            return dt.date(year, month, d)
        except ValueError:
            continue
    return dt.date(year, month, 28)


async def consumption(ctx: FarmContext, first: dt.date, last: dt.date, season_id: uuid.UUID | None, limit: int, offset: int, now: dt.datetime) -> tuple[dict[str, Any], str]:
    season = "AND a.season_id = :season" if season_id else ""
    params = {**scope_params(ctx.farm_id, ctx.user_id, ctx.role), "first": first, "last": last}
    if season_id:
        params["season"] = season_id
    rows = (await ctx.session.execute(text(_SQL.format(season=season)), params)).all()
    raw = [{"parcel_id": str(r.parcel_id), "volume_m3": float(r.volume_m3), "area_ha": None if r.area_ha is None else float(r.area_ha)} for r in rows]
    summary = summarise_consumption({"parcels": raw})
    parcels = [{**s, "area_ha": r["area_ha"], "events": int(row.events)} for s, r, row in zip(summary["parcels"], raw, rows, strict=True)]
    total = summary["total_m3"]
    page = parcels[offset: offset + limit]
    body: dict[str, Any] = {"parcels": page, "total_m3": total, "generated_at": now.isoformat(), "next_cursor": str(offset + limit) if offset + limit < len(parcels) else None}
    if season_id:
        body["season_id"] = str(season_id)
    scope = cache.advice_etag(ctx.farm_id, ctx.role, [uuid.UUID(p["parcel_id"]) for p in parcels], last, 0)
    return body, cache.content_etag(scope, {"parcels": page, "total": total})
