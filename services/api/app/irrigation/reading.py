"""Read-only views of the advice and the balance (G2): the stored plans ARE the cache, a read never computes nor calls a gateway.

The worker view is produced by `worker_view.advice_view` (the only redaction point); a worker's SQL does not even select
`assumptions` or `leaching_fraction`.
"""
import datetime as dt
import json
import uuid
from typing import Any

from sqlalchemy import text

from app.auth.farm_context import FarmContext
from app.domain.irrigation_last_known import select_served_plan
from app.irrigation import cache
from app.irrigation.access import visible_parcels
from app.irrigation.worker_view import advice_view

STAFF_PLAN = (
    "parcel_id, for_date, kind, total_minutes, sectors, net_need_mm, leaching_fraction, stress_level, confidence, assumptions,"
    " unavailable_reason, computed_at, ready_before_7"
)
WORKER_PLAN = (
    "parcel_id, for_date, kind, total_minutes, sectors, net_need_mm, stress_level, confidence, worker_assumptions AS assumptions,"
    " unavailable_reason, computed_at, ready_before_7"
)
STAFF_DAY = "day, et0_mm, et0_method, kc, etc_mm, rain_mm, rain_source, rain_eff_mm, irrigation_net_mm, taw_mm, raw_mm, depletion_mm, moisture_source"
WORKER_DAY = "day, et0_mm, et0_method, kc, etc_mm, rain_mm, rain_source, rain_eff_mm, irrigation_net_mm, depletion_mm"


def _f(v: Any) -> float | None:
    return None if v is None else float(v)


def _list(v: Any) -> list[Any]:
    return json.loads(v) if isinstance(v, str) else list(v or [])


def _advice(row: Any, *, staff: bool, last_known: bool) -> dict[str, Any]:
    out: dict[str, Any] = {
        "parcel_id": str(row.parcel_id), "for_date": row.for_date.isoformat(), "kind": row.kind, "total_minutes": row.total_minutes,
        "sectors": _list(row.sectors), "net_need_mm": _f(row.net_need_mm), "stress_level": row.stress_level,
        "confidence": "low" if last_known else row.confidence, "assumptions": _list(row.assumptions),
        "unavailable_reason": row.unavailable_reason, "computed_at": row.computed_at.isoformat(), "is_last_known": last_known,
        "ready_before_7": bool(row.ready_before_7),
    }
    if staff:
        out["leaching_fraction"] = _f(row.leaching_fraction)
    return out


def _placeholder(parcel_id: uuid.UUID, today: dt.date, now: dt.datetime, *, staff: bool) -> dict[str, Any]:
    """A visible parcel without any plan yet: unavailable with a reason, no number."""
    out: dict[str, Any] = {
        "parcel_id": str(parcel_id), "for_date": today.isoformat(), "kind": "unavailable", "total_minutes": None, "sectors": [],
        "net_need_mm": None, "stress_level": None, "confidence": "low", "assumptions": [], "unavailable_reason": "no_weather",
        "computed_at": now.isoformat(), "is_last_known": False, "ready_before_7": False,
    }
    if staff:
        out["leaching_fraction"] = None
    return out


def serve(rows: list[Any], parcel_id: uuid.UUID, today: dt.date, now: dt.datetime, role: str) -> dict[str, Any]:
    """Today's valid plan; else the latest older valid plan (dated, confidence lowered); else the latest unavailable one
    (its reason is the answer); else a placeholder. `rows` carry at most the latest valid and the latest unavailable plan."""
    staff = role in ("owner", "manager")
    mine = [r for r in rows if r.parcel_id == parcel_id]
    picked = select_served_plan({"plans": [{"for_date": r.for_date.isoformat(), "kind": r.kind, "confidence": r.confidence} for r in mine], "today": today.isoformat()})
    served = picked["served"]
    if served is not None:
        row = next(r for r in mine if r.for_date.isoformat() == served["for_date"] and r.kind == served["kind"])
        advice = _advice(row, staff=staff, last_known=picked["is_last_known"])
    else:
        advice = _placeholder(parcel_id, today, now, staff=staff)
    return advice_view({"role": role, "advice": advice})


async def _plans(ctx: FarmContext, parcel_ids: list[uuid.UUID], today: dt.date) -> list[Any]:
    """Per parcel, the latest valid plan and the latest unavailable one up to today (two rows at most)."""
    cols = STAFF_PLAN if ctx.role in ("owner", "manager") else WORKER_PLAN
    rows = await ctx.session.execute(
        text(f"SELECT {cols} FROM (SELECT t.*, row_number() OVER (PARTITION BY t.parcel_id, (t.kind = :na) ORDER BY t.for_date DESC) AS rn"
             " FROM irrigation_plans t WHERE t.farm_id = :farm AND t.parcel_id = ANY(:ids) AND t.parcel_archived_at IS NULL"
             " AND t.for_date <= :today) q WHERE q.rn = 1"),
        {"farm": ctx.farm_id, "ids": parcel_ids, "today": today, "na": "unavailable"},
    )
    return list(rows.all())


async def parcel_advice(ctx: FarmContext, parcel_id: uuid.UUID, today: dt.date, now: dt.datetime) -> dict[str, Any]:
    return serve(await _plans(ctx, [parcel_id], today), parcel_id, today, now, ctx.role)


async def advice_list(ctx: FarmContext, today: dt.date, now: dt.datetime, limit: int, offset: int) -> tuple[dict[str, Any], str]:
    """Advice of the caller's visible parcels only; the count and the ETag are computed on that scope."""
    visible = sorted(await visible_parcels(ctx), key=str)
    rows = await _plans(ctx, visible, today)
    items = [serve(rows, p, today, now, ctx.role) for p in visible]
    page = items[offset: offset + limit]
    body = {
        "items": page, "next_cursor": str(offset + limit) if offset + limit < len(items) else None,
        "to_irrigate_count": sum(1 for i in items if i["kind"] == "irrigate"), "generated_at": now.isoformat(),
    }
    scope = cache.advice_etag(ctx.farm_id, ctx.role, visible, today, 0)
    return body, cache.content_etag(scope, {"items": page, "count": body["to_irrigate_count"], "next": body["next_cursor"]})


async def balance(ctx: FarmContext, parcel_id: uuid.UUID, first: dt.date, last: dt.date) -> dict[str, Any]:
    """Journal of the window (<= 400 days); the worker's columns exclude the reserve and the moisture source."""
    cols = STAFF_DAY if ctx.role in ("owner", "manager") else WORKER_DAY
    rows = (await ctx.session.execute(
        text(f"SELECT {cols} FROM water_balance_days WHERE farm_id = :farm AND parcel_id = :p AND parcel_archived_at IS NULL"
             " AND day >= :first AND day <= :last ORDER BY day LIMIT 400"),
        {"farm": ctx.farm_id, "p": parcel_id, "first": first, "last": last},
    )).mappings().all()
    days = [{k: (v.isoformat() if isinstance(v, dt.date) else _f(v) if v is not None and not isinstance(v, str) else v) for k, v in r.items()} for r in rows]
    weather = (await ctx.session.execute(text("SELECT availability, reason FROM farm_weather WHERE farm_id = :farm"), {"farm": ctx.farm_id})).first()
    availability, reason = ("unavailable", "gateway_not_configured") if weather is None else (weather.availability, weather.reason)
    return {"days": days, "availability": availability, **({"reason": reason} if availability != "ok" else {})}
