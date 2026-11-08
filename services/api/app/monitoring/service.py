"""Monitoring reads and quota-bound writes (G2, G4). Every aggregate is computed on the caller's scope only."""
import datetime as dt
import hashlib
import json
import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.farm_context import NOT_FOUND, FarmContext
from app.config import get_settings
from app.domain.imagery_reliability import imagery_reliability
from app.domain.monitoring_limits import LIMITS
from app.monitoring import cache, uploads
from app.monitoring.access import visible_parcels
from app.monitoring.access_sql import STAFF_ROLES, VISIBLE_PARCELS_SQL, scope_params
from app.monitoring.weather import today_plus_seven

# One lock per farm, taken BEFORE any quota is read and held until the transaction ends.
FARM_LOCK_SQL = "SELECT pg_advisory_xact_lock(hashtextextended(CAST(:farm AS text), 0))"
STALE_AFTER = dt.timedelta(hours=24)
_COLOR_ORDER = "CASE ps.color WHEN 'red' THEN 0 WHEN 'orange' THEN 1 ELSE 2 END"


class QuotaExceeded(Exception):
    def __init__(self, code: str = "quota_exceeded") -> None:
        super().__init__(code)
        self.code = code


async def lock_farm(session: AsyncSession, farm_id: uuid.UUID) -> None:
    await session.execute(text(FARM_LOCK_SQL), {"farm": str(farm_id)})


def _scope(ctx: FarmContext) -> dict[str, Any]:
    return scope_params(ctx.farm_id, ctx.user_id, ctx.role)


# ---------------------------------------------------------------- weather
async def weather(ctx: FarmContext, now: dt.datetime | None = None) -> dict[str, Any]:
    """Last stored forecast (today to day 7) with its freshness; nothing is invented and no gateway is ever called."""
    now = now or dt.datetime.now(dt.UTC)
    located = bool(
        (await ctx.session.execute(text("SELECT location IS NOT NULL FROM farms WHERE id = :f"), {"f": ctx.farm_id})).scalar()
    )
    row = (
        await ctx.session.execute(
            text("SELECT availability, reason, fetched_at, days FROM farm_weather WHERE farm_id = :f"), {"f": ctx.farm_id}
        )
    ).mappings().first()
    if not located and (row is None or not row["days"]):
        return {"availability": "unavailable", "reason": "farm_not_located", "fetched_at": None, "days": []}
    if row is None:
        reason = "gateway_unreachable" if get_settings().weather_url else "gateway_not_configured"
        return {"availability": "unavailable", "reason": reason, "fetched_at": None, "days": []}
    availability, reason = row["availability"], row["reason"]
    if located and reason == "farm_not_located":
        reason = "gateway_unreachable" if get_settings().weather_url else "gateway_not_configured"
    if availability != "unavailable" and row["fetched_at"] is not None and now - row["fetched_at"] > STALE_AFTER:
        availability, reason = "stale", "stale"
    return {
        "availability": availability, "reason": reason,
        "fetched_at": row["fetched_at"].isoformat() if row["fetched_at"] else None,
        "days": today_plus_seven(list(row["days"] or []), now.date()),
    }


# ---------------------------------------------------------------- dashboard
def _parcel_status_json(r: Any) -> dict[str, Any]:
    return {
        "parcel_id": str(r["parcel_id"]), "name": r["name"], "color": r["color"], "reason_key": r["reason_key"],
        "reason_params": r["reason_params"], "computed_at": r["computed_at"].isoformat(),
        "data_age_at": r["data_age_at"].isoformat() if r["data_age_at"] else None,
        "imagery_reliability": r["imagery_reliability"],
    }


async def dashboard(ctx: FarmContext, limit: int, offset: int) -> tuple[dict[str, Any], str]:
    """Weather, counts and one page of parcels, on the caller's visible parcels. Returns (body, etag)."""
    ids = await visible_parcels(ctx)
    version = await cache.get_data_version(ctx.farm_id)
    key = cache.dashboard_cache_key(ctx.farm_id, ctx.role, ctx.user_id, ids, version) + f":{limit}:{offset}"
    hit = await cache.cache_get(key)
    if hit is not None:
        return hit["body"], hit["etag"]
    params = {**_scope(ctx), "limit": limit, "offset": offset}
    counts = {"red": 0, "orange": 0, "green": 0}
    for r in (
        await ctx.session.execute(
            text(f"SELECT ps.color, count(*) AS n FROM parcel_status ps WHERE ps.farm_id = :farm AND ps.parcel_id IN ({VISIBLE_PARCELS_SQL}) GROUP BY ps.color"),
            params,
        )
    ).all():
        counts[r[0]] = int(r[1])
    rows = (
        await ctx.session.execute(
            text(
                "SELECT ps.*, p.name FROM parcel_status ps JOIN parcels p ON p.id = ps.parcel_id AND p.farm_id = ps.farm_id"
                f" WHERE ps.farm_id = :farm AND ps.parcel_id IN ({VISIBLE_PARCELS_SQL})"
                f" ORDER BY {_COLOR_ORDER}, ps.rank, p.name, ps.parcel_id LIMIT :limit OFFSET :offset"
            ),
            params,
        )
    ).mappings().all()
    parcels = [_parcel_status_json(r) for r in rows]
    total = sum(counts.values())
    stable = {"weather": await weather(ctx), "parcels": parcels, "counts": counts}
    etag = hashlib.sha256(json.dumps(stable, sort_keys=True, default=str).encode()).hexdigest()[:32]
    body = {**stable, "next_cursor": str(offset + limit) if offset + limit < total else None,
            "generated_at": dt.datetime.now(dt.UTC).isoformat()}
    await cache.cache_set(key, {"body": body, "etag": etag})
    return body, etag


async def parcel_status(ctx: FarmContext, parcel_id: uuid.UUID) -> dict[str, Any]:
    row = (
        await ctx.session.execute(
            text("SELECT ps.*, p.name FROM parcel_status ps JOIN parcels p ON p.id = ps.parcel_id AND p.farm_id = ps.farm_id"
                 " WHERE ps.farm_id = :f AND ps.parcel_id = :p"),
            {"f": ctx.farm_id, "p": parcel_id},
        )
    ).mappings().first()
    if row is None:
        raise NOT_FOUND
    items = (
        await ctx.session.execute(
            text("SELECT source, severity, reason_key, reason_params, observed_at FROM parcel_status_items"
                 " WHERE farm_id = :f AND parcel_id = :p ORDER BY severity DESC, observed_at DESC"),
            {"f": ctx.farm_id, "p": parcel_id},
        )
    ).mappings().all()
    out = _parcel_status_json(row)
    out["items"] = [{**dict(i), "observed_at": i["observed_at"].isoformat()} for i in items]
    return out


# ---------------------------------------------------------------- alerts and zones
async def alerts(ctx: FarmContext, limit: int, only: uuid.UUID | None = None) -> list[dict[str, Any]]:
    """Active alerts, or the one alert `only` whatever its status (the dismissal answer carries the full schema)."""
    rows = (
        await ctx.session.execute(
            text(
                "SELECT a.id, a.parcel_id, a.crop_slug, a.type, a.severity, a.source, a.status, a.forecast_day, a.reason_key,"
                " a.reason_params, a.advice_key, a.notify_at, a.revision FROM alerts a"
                f" WHERE a.farm_id = :farm AND ((CAST(:only AS uuid) IS NULL AND a.status = 'active') OR a.id = :only)"
                f" AND a.parcel_id IN ({VISIBLE_PARCELS_SQL})"
                " ORDER BY CASE a.severity WHEN 'critical' THEN 0 WHEN 'warning' THEN 1 ELSE 2 END, a.forecast_day, a.id LIMIT :limit"
            ),
            {**_scope(ctx), "limit": limit, "only": only},
        )
    ).mappings().all()
    return [_jsonable(dict(r)) for r in rows]


def _jsonable(row: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in row.items():
        out[k] = str(v) if isinstance(v, uuid.UUID) else v.isoformat() if isinstance(v, (dt.date, dt.datetime)) else (float(v) if k == "area_ha" and v is not None else v)
    return out


async def zones(ctx: FarmContext, limit: int, only: uuid.UUID | None = None) -> list[dict[str, Any]]:
    rows = (
        await ctx.session.execute(
            text(
                "SELECT z.id, z.parcel_id, z.status, ST_AsGeoJSON(z.geometry)::json AS geometry,"
                " ST_AsGeoJSON(z.centroid)::json AS centroid, z.detected_on, z.area_ha::float8 AS area_ha, z.reason_key"
                f" FROM attention_zones z WHERE z.farm_id = :farm AND ((CAST(:only AS uuid) IS NULL AND z.status IN ('open', 'visited'))"
                f" OR z.id = :only) AND z.parcel_id IN ({VISIBLE_PARCELS_SQL}) ORDER BY z.detected_on DESC, z.id LIMIT :limit"
            ),
            {**_scope(ctx), "limit": limit, "only": only},
        )
    ).mappings().all()
    return [_jsonable(dict(r)) for r in rows]


async def dismiss(ctx: FarmContext, table: str, object_id: uuid.UUID) -> dict[str, Any]:
    """Staff dismisses an alert or a zone (never a physical delete)."""
    if table == "alerts":
        await ctx.session.execute(
            text("UPDATE alerts SET status = 'dismissed', updated_at = now() WHERE id = :i AND farm_id = :f"),
            {"i": object_id, "f": ctx.farm_id},
        )
    else:
        await ctx.session.execute(
            text("UPDATE attention_zones SET status = 'dismissed' WHERE id = :i AND farm_id = :f"), {"i": object_id, "f": ctx.farm_id}
        )
    await ctx.session.commit()
    await cache.bump_data_version(ctx.farm_id)
    rows = await (alerts(ctx, 1, object_id) if table == "alerts" else zones(ctx, 1, object_id))
    return rows[0] if rows else {"id": str(object_id), "status": "dismissed"}


# ---------------------------------------------------------------- vigor
def months_between(start: dt.date, end: dt.date) -> int:
    """Calendar months touched by the window, both ends included."""
    return (end.year - start.year) * 12 + end.month - start.month + 1


async def vigor_series(ctx: FarmContext, parcel_id: uuid.UUID, start: dt.date, end: dt.date) -> dict[str, Any]:
    rows = (
        await ctx.session.execute(
            text(
                "SELECT * FROM (SELECT acquired_on, vigor_mean::float8 AS vigor, plant_moisture_mean::float8 AS plant_moisture,"
                " clear_pct::float8 AS clear_pct FROM parcel_vigor_points WHERE farm_id = :f AND parcel_id = :p AND valid"
                " AND acquired_on BETWEEN :s AND :e ORDER BY acquired_on DESC LIMIT :n) t ORDER BY acquired_on"
            ),
            {"f": ctx.farm_id, "p": parcel_id, "s": start, "e": end, "n": LIMITS["series_points"]},
        )
    ).mappings().all()
    last_map = (
        await ctx.session.execute(
            text("SELECT id, acquired_on FROM vigor_maps WHERE farm_id = :f AND parcel_id = :p ORDER BY acquired_on DESC LIMIT 1"),
            {"f": ctx.farm_id, "p": parcel_id},
        )
    ).first()
    processing = (
        await ctx.session.execute(
            text("SELECT 1 FROM monitoring_jobs WHERE farm_id = :f AND parcel_id = :p AND state IN ('queued', 'running') LIMIT 1"),
            {"f": ctx.farm_id, "p": parcel_id},
        )
    ).first() is not None
    return {
        "points": [{**dict(r), "acquired_on": r["acquired_on"].isoformat()} for r in rows],
        "reliability": await _reliability(ctx, parcel_id),
        "last_valid_map": None if last_map is None else {"map_id": str(last_map[0]), "acquired_on": last_map[1].isoformat()},
        "processing": processing,
    }


async def _reliability(ctx: FarmContext, parcel_id: uuid.UUID) -> str:
    row = (
        await ctx.session.execute(
            text("SELECT COALESCE(area_calc_ha, area_declared_ha, 0)::float8 AS area, greenhouse FROM parcels WHERE id = :p AND farm_id = :f"),
            {"p": parcel_id, "f": ctx.farm_id},
        )
    ).first()
    if row is None:
        return "ok"
    min_area = (await ctx.session.execute(text("SELECT value FROM monitoring_params WHERE key = 'min_area_ha'"))).scalar()
    return imagery_reliability(float(row[0]), bool(row[1]), float(min_area if min_area is not None else 0.3))


def _leap(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def campaign_start(today: dt.date) -> dt.date:
    """Default campaign start: 1 September."""
    year = today.year if today >= dt.date(today.year, 9, 1) else today.year - 1
    return dt.date(year, 9, 1)


async def vigor_compare(ctx: FarmContext, parcel_id: uuid.UUID, today: dt.date | None = None) -> dict[str, Any]:
    """Current campaign against the previous one, aligned by day of campaign; no extrapolation."""
    today = today or dt.datetime.now(dt.UTC).date()
    season_start = (
        await ctx.session.execute(
            text("SELECT started_at FROM seasons WHERE farm_id = :f AND field_id = :p AND ended_at IS NULL ORDER BY started_at DESC LIMIT 1"),
            {"f": ctx.farm_id, "p": parcel_id},
        )
    ).scalar()
    start = season_start if season_start is not None and season_start <= today else campaign_start(today)
    prev_start = start - dt.timedelta(days=366 if start > dt.date(start.year, 2, 28) and _leap(start.year) or start <= dt.date(start.year, 2, 28) and _leap(start.year - 1) else 365)
    elapsed = (today - start).days

    async def points(s: dt.date, e: dt.date) -> list[dict[str, Any]]:
        rows = (
            await ctx.session.execute(
                text("SELECT acquired_on, vigor_mean::float8 AS vigor, plant_moisture_mean::float8 AS plant_moisture FROM parcel_vigor_points"
                     " WHERE farm_id = :f AND parcel_id = :p AND valid AND acquired_on BETWEEN :s AND :e ORDER BY acquired_on LIMIT :n"),
                {"f": ctx.farm_id, "p": parcel_id, "s": s, "e": e, "n": LIMITS["compare_points"]},
            )
        ).mappings().all()
        return [{"day_of_campaign": (r["acquired_on"] - s).days, "acquired_on": r["acquired_on"].isoformat(),
                 "vigor": r["vigor"], "plant_moisture": r["plant_moisture"]} for r in rows]

    current = await points(start, today)
    previous = await points(prev_start, prev_start + dt.timedelta(days=elapsed))
    return {"reference_available": bool(previous), "current": current, "previous": previous}


async def map_url(ctx: FarmContext, parcel_id: uuid.UUID, scene_id: uuid.UUID) -> dict[str, Any]:
    row = (
        await ctx.session.execute(
            text("SELECT map_key, acquired_on FROM vigor_maps WHERE scene_id = :s AND farm_id = :f AND parcel_id = :p"),
            {"s": scene_id, "f": ctx.farm_id, "p": parcel_id},
        )
    ).first()
    if row is None:
        raise NOT_FOUND
    return {
        "url": uploads.signed_map_url(row[0]),
        "expires_at": (dt.datetime.now(dt.UTC) + dt.timedelta(seconds=900)).isoformat(), "acquired_on": row[1].isoformat(),
    }


async def request_reprocess(ctx: FarmContext, parcel_id: uuid.UUID) -> uuid.UUID:
    """Queue a reprocessing job; quotas are counted under the farm lock in the same transaction as the insert."""
    await lock_farm(ctx.session, ctx.farm_id)
    per_day = (
        await ctx.session.execute(
            text("SELECT count(*) FROM monitoring_jobs WHERE farm_id = :f AND parcel_id = :p AND kind = 'reprocess'"
                 " AND created_at >= date_trunc('day', now())"),
            {"f": ctx.farm_id, "p": parcel_id},
        )
    ).scalar_one()
    active = (
        await ctx.session.execute(
            text("SELECT count(*) FROM monitoring_jobs WHERE farm_id = :f AND kind = 'reprocess' AND state IN ('queued', 'running')"), {"f": ctx.farm_id}
        )
    ).scalar_one()
    if per_day >= LIMITS["reprocess_per_parcel_day"] or active >= LIMITS["imagery_jobs_per_farm"]:
        raise QuotaExceeded
    job = uuid.uuid4()
    await ctx.session.execute(
        text("INSERT INTO monitoring_jobs (id, farm_id, parcel_id, kind, state, requested_by) VALUES (:i, :f, :p, 'reprocess', 'queued', :u)"),
        {"i": job, "f": ctx.farm_id, "p": parcel_id, "u": ctx.user_id},
    )
    await ctx.session.commit()
    return job


# ---------------------------------------------------------------- observations
async def create_observation(
    session: AsyncSession, farm_id: uuid.UUID, user_id: uuid.UUID, zone_id: uuid.UUID, observation_id: uuid.UUID,
    note: str, photo_id: uuid.UUID | None,
) -> bool:
    """Insert an observation under the farm lock. Returns False when the id already exists (idempotent replay)."""
    await lock_farm(session, farm_id)
    zone = (
        await session.execute(text("SELECT parcel_id FROM attention_zones WHERE id = :z AND farm_id = :f"), {"z": zone_id, "f": farm_id})
    ).first()
    if zone is None:
        raise NOT_FOUND
    known = (await session.execute(text("SELECT 1 FROM zone_observations WHERE id = :i"), {"i": observation_id})).first()
    if known is not None:
        return False
    in_zone = (await session.execute(text("SELECT count(*) FROM zone_observations WHERE zone_id = :z AND farm_id = :f"), {"z": zone_id, "f": farm_id})).scalar_one()
    in_year = (
        await session.execute(
            text("SELECT count(*) FROM zone_observations WHERE farm_id = :f AND created_at >= now() - interval '1 year'"), {"f": farm_id}
        )
    ).scalar_one()
    if in_zone >= LIMITS["observations_per_zone"] or in_year >= LIMITS["observations_per_farm_year"]:
        raise QuotaExceeded
    key = await uploads.consume_photo(session, farm_id, user_id, photo_id) if photo_id else None
    await session.execute(
        text("INSERT INTO zone_observations (id, farm_id, zone_id, parcel_id, author_id, note, photo_key)"
             " VALUES (:i, :f, :z, :p, :u, :n, :k)"),
        {"i": observation_id, "f": farm_id, "z": zone_id, "p": zone[0], "u": user_id, "n": note, "k": key},
    )
    await session.execute(  # only the server moves a zone to visited; dismissed and resolved zones are never reopened
        text("UPDATE attention_zones SET status = 'visited' WHERE id = :z AND farm_id = :f AND status = 'open'"), {"z": zone_id, "f": farm_id}
    )
    return True


# ---------------------------------------------------------------- summary
def _weather_code(day: dict[str, Any] | None) -> str | None:
    code = None if day is None else day.get("icon") or day.get("code")
    return str(code) if code and code != "unknown" else None  # "unknown" is the weather view's placeholder, not a code


async def summary_today(ctx: FarmContext, today: dt.date | None = None) -> dict[str, Any]:
    """Red parcels first, then orange, on the caller's scope; green ones have nothing to read."""
    rows = (
        await ctx.session.execute(
            text(
                f"SELECT ps.parcel_id, ps.color, ps.reason_key FROM parcel_status ps WHERE ps.farm_id = :farm AND ps.color IN ('red', 'orange')"
                f" AND ps.parcel_id IN ({VISIBLE_PARCELS_SQL}) ORDER BY {_COLOR_ORDER}, ps.rank, ps.parcel_id LIMIT :limit"
            ),
            {**_scope(ctx), "limit": LIMITS["page_max"]},
        )
    ).all()
    lang = (await ctx.session.execute(text("SELECT language FROM users WHERE id = :u"), {"u": ctx.user_id})).scalar()
    w = await weather(ctx)
    first = w["days"][0] if w["days"] else None
    return {
        "summary_date": (today or dt.datetime.now(dt.UTC).date()).isoformat(),
        "locale": lang if lang in ("ary", "ar", "fr") else "fr",
        "items": [{"parcel_id": str(r[0]), "color": r[1], "reason_key": r[2]} for r in rows],
        "weather_code": _weather_code(first),
    }


async def save_settings(ctx: FarmContext, summary_hour: int, alerts_enabled: bool) -> dict[str, Any]:
    await ctx.session.execute(
        text("INSERT INTO notification_prefs (farm_id, user_id, summary_hour, alerts_enabled) VALUES (:f, :u, :h, :a)"
             " ON CONFLICT (farm_id, user_id) DO UPDATE SET summary_hour = :h, alerts_enabled = :a"),
        {"f": ctx.farm_id, "u": ctx.user_id, "h": summary_hour, "a": alerts_enabled},
    )
    await ctx.session.commit()
    return {"summary_hour": summary_hour, "alerts_enabled": alerts_enabled}


# ---------------------------------------------------------------- notification workers
async def notification_recipients(session: AsyncSession, farm_id: uuid.UUID) -> dict[uuid.UUID, list[uuid.UUID]]:
    """Every active member and the parcels visible to them (an empty list for a worker without parcel)."""
    members = (
        await session.execute(
            text("SELECT user_id, role FROM farm_members WHERE farm_id = :f AND removed_at IS NULL"), {"f": farm_id}
        )
    ).all()
    out: dict[uuid.UUID, list[uuid.UUID]] = {}
    for user_id, role in members:
        rows = await session.execute(text(VISIBLE_PARCELS_SQL), scope_params(farm_id, user_id, role))
        out[user_id] = [r[0] for r in rows.all()]
    return out


__all__ = ["STAFF_ROLES", "QuotaExceeded"]
