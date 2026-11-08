"""Attention zones: resolves a zone once the vigor is back above the reference threshold on two valid scenes (FR-011).

Detection thresholds (`anomaly_drop`, `anomaly_min_pixels`, `anomaly_resolved_vigor`) are agronomic reference values: when the
reference table does not carry them nothing is detected or resolved. Zone creation from rasters belongs to the imagery story.
"""
import json
import uuid
from typing import Any

from access_sql import VISIBLE_PARCELS_SQL, asyncpg_query, scope_params
from anomaly import is_resolved
from monitoring_db import STAFF_SCOPE_USER, bump_data_version, dsn, param


async def detect_zones(ctx: dict[str, Any]) -> int:
    import asyncpg

    resolved = 0
    conn = await asyncpg.connect(dsn())
    try:
        threshold = await param(conn, "anomaly_resolved_vigor")
        if threshold is None:
            return 0
        for farm in [r["id"] for r in await conn.fetch("SELECT id FROM farms WHERE deleted_at IS NULL")]:
            async with conn.transaction():
                await conn.execute("SELECT pg_advisory_xact_lock(hashtextextended($1, 0))", f"monitoring:{farm}")  # one detection per farm
                resolved += await _farm(conn, farm, float(threshold))
            await bump_data_version(farm)
    finally:
        await conn.close()
    return resolved


async def _farm(conn: Any, farm: uuid.UUID, threshold: float) -> int:
    query, args = asyncpg_query(
        f"SELECT z.id, z.parcel_id FROM attention_zones z WHERE z.farm_id = :farm AND z.status IN ('open', 'visited')"
        f" AND z.parcel_id IN ({VISIBLE_PARCELS_SQL})",
        scope_params(farm, STAFF_SCOPE_USER, "owner"),
    )
    n = 0
    for z in await conn.fetch(query, *args):
        recent = [float(r["vigor_mean"]) for r in await conn.fetch(
            "SELECT vigor_mean FROM parcel_vigor_points WHERE parcel_id = $1 AND valid ORDER BY acquired_on DESC LIMIT 2", z["parcel_id"])][::-1]
        if is_resolved(recent, threshold):
            await conn.execute("UPDATE attention_zones SET status = 'resolved' WHERE id = $1 AND farm_id = $2", z["id"], farm)
            n += 1
    return n


__all__ = ["detect_zones", "json"]
