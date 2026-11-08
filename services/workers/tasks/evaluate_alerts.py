"""Weather alerts every 3 hours: thresholds x forecast, per farm, on the parcels the shared predicate makes visible.

Idempotent: one alert per dedup key (upsert, `revision` + 1 when the severity changes); a forecast that disappears resolves
the alert; a passed day expires it. The notification of a frost is scheduled the evening before, before 18:00 (SC-003).
"""
import datetime as dt
import json
import uuid
from typing import Any

from access_sql import VISIBLE_PARCELS_SQL, asyncpg_query, scope_params
from alert_rules import dedup_key, evaluate_day
from monitoring_db import STAFF_SCOPE_USER, bump_data_version, dsn, param
from notification_schedule import frost_notify_at
from weather_thresholds import thresholds_for

ALERTS_PER_PARCEL = 20


async def evaluate_alerts(ctx: dict[str, Any], now: dt.datetime | None = None) -> int:
    import asyncpg

    now = now or dt.datetime.now(dt.UTC)
    written = 0
    conn = await asyncpg.connect(dsn())
    try:
        farms = [r["id"] for r in await conn.fetch("SELECT id FROM farms WHERE deleted_at IS NULL")]
        for farm in farms:
            async with conn.transaction():
                await conn.execute("SELECT pg_advisory_xact_lock(hashtextextended($1, 0))", f"monitoring:{farm}")  # one recompute per farm
                written += await _farm(conn, farm, now)
            await bump_data_version(farm)
    finally:
        await conn.close()
    return written


async def _farm(conn: Any, farm: uuid.UUID, now: dt.datetime) -> int:
    weather = await conn.fetchrow("SELECT days FROM farm_weather WHERE farm_id = $1", farm)
    days = json.loads(weather["days"]) if weather and isinstance(weather["days"], str) else (list(weather["days"]) if weather else [])
    thresholds = [dict(r) for r in await conn.fetch("SELECT * FROM crop_weather_thresholds")]
    notify_hour = int(await param(conn, "frost_notify_hour", 17))
    query, args = asyncpg_query(
        f"SELECT v.id, c.slug AS crop_slug, s.id AS season_id, COALESCE(s.stage_corrected, s.stage_estimated) AS stage"
        f" FROM ({VISIBLE_PARCELS_SQL}) v JOIN seasons s ON s.field_id = v.id AND s.farm_id = :farm AND s.ended_at IS NULL"
        " JOIN crops c ON c.id = s.crop_id",
        scope_params(farm, STAFF_SCOPE_USER, "owner"),
    )
    written = 0
    for p in await conn.fetch(query, *args):
        keep: set[str] = set()
        for day in days:
            for a in evaluate_day(thresholds_for(thresholds, p["crop_slug"], p["stage"] or ""), day):
                key = dedup_key(farm_id=str(farm), parcel_id=str(p["id"]), crop_slug=p["crop_slug"], type=a["type"], forecast_day=day["date"])
                keep.add(key)
                notify_at = frost_notify_at(day["date"], now, notify_hour)[0] if a["type"] == "frost" else None
                active = await conn.fetchval("SELECT count(*) FROM alerts WHERE parcel_id = $1 AND status = 'active' AND dedup_key <> $2", p["id"], key)
                if active >= ALERTS_PER_PARCEL:
                    continue
                await conn.execute(
                    "INSERT INTO alerts (id, farm_id, parcel_id, season_id, crop_slug, type, severity, forecast_day, reason_key, reason_params,"
                    " advice_key, notify_at, dedup_key) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10::jsonb,$11,$12,$13)"
                    " ON CONFLICT (dedup_key) DO UPDATE SET severity = $7, reason_params = $10::jsonb, status = 'active',"
                    " revision = alerts.revision + CASE WHEN alerts.severity <> $7 OR alerts.status <> 'active' THEN 1 ELSE 0 END,"
                    " updated_at = now() WHERE alerts.status <> 'dismissed'",
                    uuid.uuid4(), farm, p["id"], p["season_id"], p["crop_slug"], a["type"], a["severity"], dt.date.fromisoformat(day["date"]),
                    a["reason_key"], json.dumps(a["params"]), a["advice_key"], notify_at, key,
                )
                written += 1
        await conn.execute(
            "UPDATE alerts SET status = 'resolved', updated_at = now() WHERE parcel_id = $1 AND status = 'active' AND NOT (dedup_key = ANY($2))",
            p["id"], list(keep),
        )
    await conn.execute("UPDATE alerts SET status = 'expired', updated_at = now() WHERE farm_id = $1 AND status = 'active' AND forecast_day < $2", farm, now.date())
    return written
