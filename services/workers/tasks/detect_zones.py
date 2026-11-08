"""Attention zones (FR-011): new zones from the vigor-drop grid of each parcel, and resolution once the vigor recovers.

Detection thresholds (`anomaly_drop`, `anomaly_min_pixels`, `anomaly_resolved_vigor`) are agronomic reference values read from
`ctx["params"]` or, failing that, `monitoring_params`; when absent nothing is detected or resolved. The raster reading is
injected as `ctx["grid_for"](parcel_id)` -> {drop, valid, bounds}. Quotas: 5 open zones per parcel, 200 per farm.
"""
import datetime as dt
import json
import uuid
from typing import Any

from access_sql import VISIBLE_PARCELS_SQL, asyncpg_query, scope_params
from anomaly import is_resolved
from monitoring_db import STAFF_SCOPE_USER, bump_data_version, dsn, param
from zones import detect_zones as find_zones

ZONES_PER_PARCEL = 5
ZONES_PER_FARM = 200
ACTIVE = ("open", "visited")


async def _threshold(conn: Any, ctx: dict[str, Any], key: str) -> Any:
    params = ctx.get("params")
    return params.get(key) if params is not None else await param(conn, key)


async def detect_zones(ctx: dict[str, Any], now: dt.datetime | None = None, farm_id: uuid.UUID | None = None) -> int:
    import asyncpg

    now = now or dt.datetime.now(dt.UTC)
    changed = 0
    conn = await asyncpg.connect(dsn())
    try:
        farms = [farm_id] if farm_id else [r["id"] for r in await conn.fetch("SELECT id FROM farms WHERE deleted_at IS NULL")]
        for farm in farms:
            async with conn.transaction():
                await conn.execute("SELECT pg_advisory_xact_lock(hashtextextended($1, 0))", f"monitoring:{farm}")  # one detection per farm
                changed += await _farm(conn, ctx, farm, now)
            await bump_data_version(farm)
    finally:
        await conn.close()
    return changed


async def _farm(conn: Any, ctx: dict[str, Any], farm: uuid.UUID, now: dt.datetime) -> int:
    resolved_at = await _threshold(conn, ctx, "anomaly_resolved_vigor")
    drop = await _threshold(conn, ctx, "anomaly_drop")
    min_pixels = await _threshold(conn, ctx, "anomaly_min_pixels")
    query, args = asyncpg_query(f"SELECT id FROM ({VISIBLE_PARCELS_SQL}) v", scope_params(farm, STAFF_SCOPE_USER, "owner"))
    parcels = [r["id"] for r in await conn.fetch(query, *args)]
    changed = 0
    if resolved_at is not None:
        changed += await _resolve(conn, farm, parcels, float(resolved_at))
    grid_for = ctx.get("grid_for")
    if drop is None or min_pixels is None or grid_for is None:
        return changed
    farm_open = await conn.fetchval("SELECT count(*) FROM attention_zones WHERE farm_id = $1 AND status = ANY($2)", farm, list(ACTIVE))
    for parcel in parcels:
        grid = grid_for(parcel)
        if grid is None:
            continue
        found = find_zones(grid["drop"], grid["valid"], float(drop), int(min_pixels), tuple(grid["bounds"]))
        room = ZONES_PER_PARCEL - await conn.fetchval("SELECT count(*) FROM attention_zones WHERE parcel_id = $1 AND status = ANY($2)", parcel, list(ACTIVE))
        for z in found:  # strongest first
            if room <= 0 or farm_open >= ZONES_PER_FARM:
                break
            geometry = json.dumps(z["geometry"])
            if await conn.fetchval(
                "SELECT 1 FROM attention_zones WHERE parcel_id = $1 AND status IN ('open','visited','dismissed')"
                " AND ST_Intersects(geometry, ST_SetSRID(ST_GeomFromGeoJSON($2), 4326)) LIMIT 1", parcel, geometry):
                continue  # the same anomaly is already known
            await conn.execute(
                "INSERT INTO attention_zones (id, farm_id, parcel_id, geometry, centroid, detected_on, drop_score, area_ha, status, reason_key)"
                " VALUES ($1,$2,$3,ST_SetSRID(ST_GeomFromGeoJSON($4),4326),ST_SetSRID(ST_GeomFromGeoJSON($5),4326),$6,$7,$8,'open','zone.vigor_drop')",
                uuid.uuid4(), farm, parcel, geometry, json.dumps(z["centroid"]), now.date(), z["drop_score"], z["area_ha"],
            )
            room -= 1
            farm_open += 1
            changed += 1
    return changed


async def _resolve(conn: Any, farm: uuid.UUID, parcels: list[uuid.UUID], threshold: float) -> int:
    n = 0
    for z in await conn.fetch(
        "SELECT id, parcel_id FROM attention_zones WHERE farm_id = $1 AND status = ANY($2) AND parcel_id = ANY($3)", farm, list(ACTIVE), parcels):
        recent = [float(r["vigor_mean"]) for r in await conn.fetch(
            "SELECT vigor_mean FROM parcel_vigor_points WHERE parcel_id = $1 AND valid ORDER BY acquired_on DESC LIMIT 2", z["parcel_id"])][::-1]
        if is_resolved(recent, threshold):
            await conn.execute("UPDATE attention_zones SET status = 'resolved' WHERE id = $1 AND farm_id = $2", z["id"], farm)
            n += 1
    return n
