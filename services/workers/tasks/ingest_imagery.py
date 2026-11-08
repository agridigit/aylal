"""Imagery ingestion: scenes of a public tile, and the publication rule of a scene over a parcel (SC-004).

Only a public tile identifier and dates leave to the gateway. A scene under 80 percent clear over the parcel is never
published: it is logged `rejected_cloud` and no point is written. Without a configured gateway nothing is created.
"""
import asyncio
import datetime as dt
import os
import uuid
from typing import Any

from gateways import ImageryGateway
from imagery_reliability import imagery_reliability
from monitoring_db import dsn, param
from vigor import is_scene_publishable

REJECTED = "rejected_cloud"


async def publish_scene_stats(
    conn: Any, *, farm_id: uuid.UUID, parcel_id: uuid.UUID, scene_id: uuid.UUID, acquired_on: dt.date, stats: dict[str, Any]
) -> str:
    """Write the point of a clear-enough scene (idempotent per parcel and scene) and log the outcome."""
    clear = float(stats.get("clear_pct") or 0.0)
    vigor, moisture = stats.get("vigor_mean"), stats.get("plant_moisture_mean")
    min_clear = float(await param(conn, "cloud_min_clear_pct", 80))
    if not is_scene_publishable(clear, min_clear) or (vigor is None and moisture is None):
        outcome = REJECTED
    elif vigor is None or moisture is None:
        outcome = "error"
    else:
        outcome = "ok"
    async with conn.transaction():
        if outcome == "ok":
            p = await conn.fetchrow(
                "SELECT COALESCE(area_calc_ha, area_declared_ha, 0) AS area, greenhouse FROM parcels WHERE id = $1 AND farm_id = $2", parcel_id, farm_id)
            min_area = float(await param(conn, "min_area_ha", 0.3))
            reliability = imagery_reliability(float(p["area"]), p["greenhouse"], min_area) if p else "ok"
            await conn.execute(
                "INSERT INTO parcel_vigor_points (id, farm_id, parcel_id, scene_id, acquired_on, vigor_mean, plant_moisture_mean, clear_pct, reliability)"
                " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9) ON CONFLICT (parcel_id, scene_id) DO UPDATE SET vigor_mean = $6, plant_moisture_mean = $7,"
                " clear_pct = $8, reliability = $9",
                uuid.uuid4(), farm_id, parcel_id, scene_id, acquired_on, vigor, moisture, clear, reliability,
            )
        await conn.execute(
            "INSERT INTO parcel_scene_log (farm_id, parcel_id, scene_id, outcome) VALUES ($1,$2,$3,$4)"
            " ON CONFLICT (parcel_id, scene_id) DO UPDATE SET outcome = $4, logged_at = now()",
            farm_id, parcel_id, scene_id, outcome,
        )
    return outcome


async def ingest_imagery(ctx: dict[str, Any], *, tile_id: str, date_from: dt.date, date_to: dt.date) -> int:
    """Register the scenes of a tile not already known; returns how many were added."""
    import asyncpg

    gateway = ctx.get("gateway") or ImageryGateway(
        url=os.environ.get("AYLAL_IMAGERY_URL", ""),
        allowed_hosts=[h for h in os.environ.get("AYLAL_EXTERNAL_ALLOWED_HOSTS", "").split(",") if h.strip()],
    )
    if not gateway.configured():
        return 0
    answer = await asyncio.to_thread(gateway.scenes, mgrs=tile_id, date_from=date_from.isoformat(), date_to=date_to.isoformat())
    if answer.get("availability") != "ok":
        return 0
    added = 0
    conn = await asyncpg.connect(dsn())
    try:
        async with conn.transaction():
            await conn.execute("SELECT pg_advisory_xact_lock(hashtextextended($1, 0))", f"imagery:{tile_id}")
            await conn.execute("INSERT INTO imagery_tiles (tile_id) VALUES ($1) ON CONFLICT DO NOTHING", tile_id)
            for scene in answer["scenes"]:
                on = dt.date.fromisoformat(str(scene["acquired_on"]))
                if await conn.fetchval("SELECT 1 FROM imagery_scenes WHERE tile_id = $1 AND acquired_on = $2", tile_id, on):
                    continue
                sid = uuid.uuid4()
                await conn.execute(
                    "INSERT INTO imagery_scenes (id, tile_id, acquired_on, cloud_pct_scene, raster_key) VALUES ($1,$2,$3,$4,$5)",
                    sid, tile_id, on, scene.get("cloud_pct_scene"), scene.get("raster_key") or f"rasters/{sid}",
                )
                added += 1
            if answer["scenes"]:
                await conn.execute("UPDATE imagery_tiles SET last_ingested_on = $2 WHERE tile_id = $1", tile_id, date_to)
    finally:
        await conn.close()
    return added
