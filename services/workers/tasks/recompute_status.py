"""Parcel status every hour and after a signal: signals of each source -> colour, reason, contributors (FR-012, FR-013).

Per farm, under the `monitoring:{farm}` lock, on the parcels the shared predicate makes visible (archived ones are skipped).
A source that does not exist yet (irrigation F4, health F5) simply contributes nothing.
"""
import datetime as dt
import json
import uuid
from typing import Any

from access_sql import VISIBLE_PARCELS_SQL, asyncpg_query, scope_params
from imagery_reliability import imagery_reliability
from monitoring_db import STAFF_SCOPE_USER, bump_data_version, dsn, param
from parcel_status import parcel_status, sort_parcels
from weather_thresholds import thresholds_for

TTL_S = 24 * 3600


def _signal(source: str, severity: str, reason_key: str, observed: dt.datetime, ref: Any, params: dict[str, Any]) -> dict[str, Any]:
    return {"source": source, "severity": severity, "reason_key": reason_key, "observed_at": observed.isoformat(), "ttl_s": TTL_S,
            "source_ref": ref, "params": params}


async def recompute_status(ctx: dict[str, Any], now: dt.datetime | None = None) -> int:
    import asyncpg

    now = now or dt.datetime.now(dt.UTC)
    total = 0
    conn = await asyncpg.connect(dsn())
    try:
        for farm in [r["id"] for r in await conn.fetch("SELECT id FROM farms WHERE deleted_at IS NULL")]:
            async with conn.transaction():
                await conn.execute("SELECT pg_advisory_xact_lock(hashtextextended($1, 0))", f"monitoring:{farm}")  # serialises recomputes
                total += await _farm(conn, farm, now)
            await bump_data_version(farm)
    finally:
        await conn.close()
    return total


async def _farm(conn: Any, farm: uuid.UUID, now: dt.datetime) -> int:
    min_area = float(await param(conn, "min_area_ha", 0.3))
    thresholds = [dict(r) for r in await conn.fetch("SELECT * FROM crop_weather_thresholds")]
    query, args = asyncpg_query(
        f"SELECT p.id, p.name, COALESCE(p.area_calc_ha, p.area_declared_ha, 0) AS area, p.greenhouse FROM parcels p"
        f" WHERE p.id IN ({VISIBLE_PARCELS_SQL})",
        scope_params(farm, STAFF_SCOPE_USER, "owner"),
    )
    computed: list[dict[str, Any]] = []
    for p in await conn.fetch(query, *args):
        signals: list[dict[str, Any]] = []
        for a in await conn.fetch("SELECT id, severity, reason_key, reason_params, updated_at FROM alerts WHERE parcel_id = $1 AND status = 'active'", p["id"]):
            signals.append(_signal("weather_alert", "act" if a["severity"] == "critical" else "watch", a["reason_key"].replace("alert.", "status."), a["updated_at"], a["id"], {}))
        for z in await conn.fetch("SELECT id, detected_on FROM attention_zones WHERE parcel_id = $1 AND status IN ('open', 'visited')", p["id"]):
            signals.append(_signal("vigor_anomaly", "watch", "status.vigor_zone", now, z["id"], {}))
        for o in await conn.fetch("SELECT operation_id FROM operation_parcels WHERE parcel_id = $1 AND status = 'planned' AND performed_on < $2", p["id"], now.date()):
            signals.append(_signal("overdue_operations", "watch", "status.overdue", now, o["operation_id"], {}))
        doubts: list[str] = []
        if not signals and await _unknown_threshold(conn, p["id"], farm, thresholds):
            doubts.append("unknown_threshold")
        status = parcel_status(signals, now, doubts)
        computed.append({"p": p, "signals": signals, "status": status, "contributors": len(status["items"])})
    ordered = sort_parcels([{"id": c["p"]["id"], "color": c["status"]["color"], "contributors": c["contributors"], "name": c["p"]["name"]} for c in computed])
    rank = {o["id"]: i for i, o in enumerate(ordered)}
    for c in computed:
        p, s = c["p"], c["status"]
        await conn.execute(
            "INSERT INTO parcel_status (parcel_id, farm_id, color, reason_key, reason_params, rank, computed_at, data_age_at, imagery_reliability)"
            " VALUES ($1,$2,$3,$4,'{}'::jsonb,$5,$6,$6,$7) ON CONFLICT (parcel_id) DO UPDATE SET color = $3, reason_key = $4, rank = $5,"
            " computed_at = $6, data_age_at = $6, imagery_reliability = $7",
            p["id"], farm, s["color"], s["reason_key"], rank[p["id"]], now, imagery_reliability(float(p["area"]), p["greenhouse"], min_area),
        )
        await conn.execute("DELETE FROM parcel_status_items WHERE parcel_id = $1", p["id"])
        by_source = {sig["source"]: sig for sig in c["signals"]}
        for item in s["items"]:
            sig = by_source.get(item["source"])
            await conn.execute(
                "INSERT INTO parcel_status_items (id, farm_id, parcel_id, source, severity, reason_key, reason_params, source_ref, observed_at)"
                " VALUES ($1,$2,$3,$4,$5,$6,'{}'::jsonb,$7,$8)",
                uuid.uuid4(), farm, p["id"], item["source"], item["severity"], item["reason_key"], sig["source_ref"] if sig else None,
                dt.datetime.fromisoformat(item["observed_at"]),
            )
    return len(computed)


async def _unknown_threshold(conn: Any, parcel: uuid.UUID, farm: uuid.UUID, thresholds: list[dict[str, Any]]) -> bool:
    """Doubt: a freezing forecast and no validated threshold for the crop and stage (orange, never a false green)."""
    row = await conn.fetchrow("SELECT days FROM farm_weather WHERE farm_id = $1", farm)
    raw = row["days"] if row else []
    days = json.loads(raw) if isinstance(raw, str) else list(raw or [])
    if not any(d.get("tmin", 99) <= 0 for d in days):
        return False
    for s in await conn.fetch(
        "SELECT c.slug, COALESCE(s.stage_corrected, s.stage_estimated) AS stage FROM seasons s JOIN crops c ON c.id = s.crop_id"
        " WHERE s.field_id = $1 AND s.ended_at IS NULL", parcel,
    ):
        if thresholds_for(thresholds, s["slug"], s["stage"] or "") is None:
            return True
    return False
