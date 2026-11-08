"""Nightly (03:00 local) and on-demand computation of the daily advice, per farm, under the `irrigation:{farm}` lock.

Only the parcels the shared predicate makes visible are computed (an archived parcel is neither computed nor notified). The queued
recompute jobs of the farm are coalesced by the API (one per parcel, oldest date); this task consumes them. Time is the injected clock.
"""
import datetime as dt
import uuid
from typing import Any

from access_sql import VISIBLE_PARCELS_SQL, asyncpg_query, scope_params
from clock import instant, is_before_local_hour, local_hour
from irrigation_db import AsyncpgDb, bump_irrigation_version, clock_for
from irrigation_engine import READY_HOUR, compute_parcel_plan
from monitoring_db import STAFF_SCOPE_USER, dsn

RUN_HOUR = 3


async def compute_irrigation_plans(ctx: dict[str, Any], farm_id: uuid.UUID | str | None = None, now: str | dt.datetime | None = None) -> dict[str, Any]:
    import asyncpg

    clock = clock_for(now, ctx.get("clock"))
    moment = instant(clock)
    computed: list[str] = []
    changed_farms: list[uuid.UUID] = []
    conn = await asyncpg.connect(dsn())
    try:
        farms = [uuid.UUID(str(farm_id))] if farm_id else [r["id"] for r in await conn.fetch("SELECT id FROM farms WHERE deleted_at IS NULL")]
        for farm in farms:
            async with conn.transaction():
                await conn.execute("SELECT pg_advisory_xact_lock(hashtextextended($1, 0))", f"irrigation:{farm}")  # one pass per farm
                jobs = {r["parcel_id"]: r for r in await conn.fetch("SELECT id, parcel_id, from_date FROM irrigation_jobs WHERE farm_id = $1 AND state = 'queued'", farm)}
                if jobs:
                    await conn.execute("UPDATE irrigation_jobs SET state = 'running' WHERE farm_id = $1 AND id = ANY($2)", farm, [j["id"] for j in jobs.values()])
                query, args = asyncpg_query(f"SELECT p.id FROM parcels p WHERE p.id IN ({VISIBLE_PARCELS_SQL}) ORDER BY p.id", scope_params(farm, STAFF_SCOPE_USER, "owner"))
                db = AsyncpgDb(conn)
                for row in await conn.fetch(query, *args):
                    job = jobs.get(row["id"])
                    plan = await compute_parcel_plan(db, farm, row["id"], clock, job["from_date"] if job else None)
                    if plan is not None:
                        computed.append(str(row["id"]))
                        if plan.get("plan_changed") and farm not in changed_farms:
                            changed_farms.append(farm)
                if jobs:
                    await conn.execute("UPDATE irrigation_jobs SET state = 'done' WHERE farm_id = $1 AND id = ANY($2)", farm, [j["id"] for j in jobs.values()])
            await bump_irrigation_version(farm)
    finally:
        await conn.close()
    redis = ctx.get("redis")
    if redis is not None:
        for farm in changed_farms:  # the parcel status reads the advice: one recompute per farm, only when an advice changed
            await redis.enqueue_job("recompute_status", farm_id=farm)
    return {"parcels": computed, "ready_before_7": is_before_local_hour(moment, READY_HOUR)}


async def nightly_irrigation_plans(ctx: dict[str, Any]) -> dict[str, Any]:
    """Cron entry: runs only at 03:00 local (the schedule fires at both UTC hours the zone can map to)."""
    if local_hour(instant(clock_for(None, ctx.get("clock")))) != RUN_HOUR:
        return {"parcels": [], "ready_before_7": True, "skipped": True}
    return await compute_irrigation_plans(ctx)
