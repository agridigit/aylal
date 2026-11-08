"""Initial history of a parcel: the scenes of the last 12 months already ingested, published under the 80 percent rule.

One active job per parcel; the duration is measured (SC-002). The raster reading is injected (`ctx["tiles_for"]`,
`ctx["stats_for"]`): without it nothing is computed and the job ends `failed`, no value being invented.
"""
import datetime as dt
import uuid
from typing import Any

from imagery import backfill_window
from monitoring_db import bump_data_version, dsn
from tasks.ingest_imagery import publish_scene_stats


async def enqueue_backfill(conn: Any, *, farm_id: uuid.UUID, parcel_id: uuid.UUID) -> uuid.UUID:
    """The active backfill job of the parcel, created when there is none (never two at once)."""
    async with conn.transaction():
        await conn.execute("SELECT pg_advisory_xact_lock(hashtextextended($1, 0))", f"monitoring:{farm_id}")
        job = await conn.fetchval(
            "SELECT id FROM monitoring_jobs WHERE parcel_id = $1 AND kind = 'backfill' AND state IN ('queued','running') ORDER BY created_at LIMIT 1",
            parcel_id)
        if job is None:
            job = uuid.uuid4()
            await conn.execute("INSERT INTO monitoring_jobs (id, farm_id, parcel_id, kind, state) VALUES ($1,$2,$3,'backfill','queued')", job, farm_id, parcel_id)
    return job  # type: ignore[no-any-return]


async def backfill_parcel_vigor(ctx: dict[str, Any], *, farm_id: uuid.UUID, parcel_id: uuid.UUID, now: dt.datetime | None = None) -> str:
    import asyncpg

    now = now or dt.datetime.now(dt.UTC)
    conn = await asyncpg.connect(dsn())
    try:
        if not await conn.fetchval("SELECT 1 FROM parcels WHERE id = $1 AND farm_id = $2 AND archived_at IS NULL", parcel_id, farm_id):
            return "skipped"
        job = await enqueue_backfill(conn, farm_id=farm_id, parcel_id=parcel_id)
        started = dt.datetime.now(dt.UTC)
        await conn.execute("UPDATE monitoring_jobs SET state = 'running', started_at = $2 WHERE id = $1", job, started)
        state = "done"
        try:
            await _publish(conn, ctx, farm_id, parcel_id, now)
        except Exception:
            state = "failed"
        finished = dt.datetime.now(dt.UTC)
        await conn.execute("UPDATE monitoring_jobs SET state = $2, finished_at = $3, duration_s = $4 WHERE id = $1",
                           job, state, finished, (finished - started).total_seconds())
        await bump_data_version(farm_id)
        return state
    finally:
        await conn.close()


async def _publish(conn: Any, ctx: dict[str, Any], farm_id: uuid.UUID, parcel_id: uuid.UUID, now: dt.datetime) -> None:
    tiles_for, stats_for = ctx.get("tiles_for"), ctx.get("stats_for")
    if tiles_for is None or stats_for is None:
        raise RuntimeError("raster reading is not available")
    start, end = backfill_window(now.date())
    scenes = await conn.fetch(
        "SELECT id, acquired_on FROM imagery_scenes WHERE tile_id = ANY($1) AND acquired_on BETWEEN $2 AND $3 ORDER BY acquired_on",
        list(tiles_for(parcel_id)), start, end)
    for s in scenes:
        await publish_scene_stats(conn, farm_id=farm_id, parcel_id=parcel_id, scene_id=s["id"], acquired_on=s["acquired_on"],
                                  stats=stats_for(s["id"], parcel_id))
