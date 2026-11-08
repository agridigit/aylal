"""Periodic consumer of the queued `backfill` jobs created with each parcel (queued -> running -> done|failed).

Only `kind = 'backfill'` is consumed (reprocessing has its own consumer). A failure is isolated per job. On the periodic run
(no `farm_id`) a job must be at least `MIN_AGE_S` old so a job is never taken the instant it is created; a targeted run
(`farm_id`) takes every queued job of that farm.
"""
import datetime as dt
import uuid
from typing import Any

from monitoring_db import dsn
from tasks.backfill_parcel_vigor import backfill_parcel_vigor

MIN_AGE_S = 120


async def drain_backfill_jobs(ctx: dict[str, Any], now: dt.datetime | None = None, *, farm_id: uuid.UUID | None = None) -> int:
    import asyncpg

    now = now or dt.datetime.now(dt.UTC)
    conn = await asyncpg.connect(dsn())
    try:
        jobs = await conn.fetch(
            "SELECT id, farm_id, parcel_id FROM monitoring_jobs WHERE kind = 'backfill' AND state = 'queued'"
            " AND ($1::uuid IS NULL OR farm_id = $1) AND ($1::uuid IS NOT NULL OR created_at <= now() - make_interval(secs => $2))"
            " ORDER BY created_at", farm_id, float(MIN_AGE_S))
        handled = 0
        for job in jobs:
            try:
                await backfill_parcel_vigor(ctx, farm_id=job["farm_id"], parcel_id=job["parcel_id"], now=now)
            except Exception:
                await conn.execute("UPDATE monitoring_jobs SET state = 'failed', finished_at = now() WHERE id = $1 AND state IN ('queued','running')", job["id"])
            handled += 1
        return handled
    finally:
        await conn.close()
