"""T054 (US2) - the plan computation worker: nightly at 03:00 local, ready before 7, archived parcel excluded, one pass per farm
(advisory lock), recompute_status queued only when the advice changes, and a weather refresh schedules a computation."""
import asyncio
import datetime as dt
import uuid

import pytest

from tasks.compute_irrigation_plans import compute_irrigation_plans, nightly_irrigation_plans
from tests._f3 import run, seed_parcel
from tests._f4_us import AT_03, AT_09, DAY, NOW, SpyRedis, plan, seed_world


def test_given_the_03_00_local_run_then_the_advice_is_computed_and_flagged_ready_before_7():
    async def scenario(conn):
        farm, parcel = await seed_world(conn)
        out = await compute_irrigation_plans({}, farm_id=farm, now=AT_03)
        return out, await plan(conn, parcel)

    out, row = run(scenario)
    assert out["ready_before_7"] is True and row["kind"] == "irrigate" and row["ready_before_7"] is True


def test_given_a_run_after_7_local_then_the_plan_is_not_flagged_ready_before_7():
    async def scenario(conn):
        farm, parcel = await seed_world(conn)
        out = await compute_irrigation_plans({}, farm_id=farm, now=AT_09)
        return out, await plan(conn, parcel)

    out, row = run(scenario)
    assert out["ready_before_7"] is False and row["ready_before_7"] is False


def test_given_the_cron_entry_then_it_only_runs_at_03_00_local():
    from clock import FixedClock

    async def scenario(conn):
        farm, parcel = await seed_world(conn)
        skipped = await nightly_irrigation_plans({"clock": FixedClock(dt.datetime.fromisoformat(AT_09))})
        assert skipped.get("skipped") is True and await plan(conn, parcel) is None
        ran = await nightly_irrigation_plans({"clock": FixedClock(dt.datetime.fromisoformat(AT_03))})
        return str(parcel) in ran["parcels"], await plan(conn, parcel)

    ran, row = run(scenario)
    assert ran is True and row is not None


def test_given_an_archived_parcel_then_it_is_neither_computed_nor_planned():
    async def scenario(conn):
        farm, parcel = await seed_world(conn)
        gone = await seed_parcel(conn, farm, archived=True)
        out = await compute_irrigation_plans({}, farm_id=farm, now=NOW)
        return out, parcel, gone, await plan(conn, gone)

    out, parcel, gone, row = run(scenario)
    assert str(parcel) in out["parcels"] and str(gone) not in out["parcels"] and row is None


def test_given_a_queued_job_then_the_run_consumes_it_once_and_marks_it_done():
    async def scenario(conn):
        farm, parcel = await seed_world(conn)
        job = uuid.uuid4()
        await conn.execute("INSERT INTO irrigation_jobs (id, farm_id, parcel_id, from_date, state) VALUES ($1,$2,$3,$4,'queued')", job, farm, parcel, DAY - dt.timedelta(days=3))
        await compute_irrigation_plans({}, farm_id=farm, now=NOW)
        first = await conn.fetchval("SELECT state FROM irrigation_jobs WHERE id=$1", job)
        await compute_irrigation_plans({}, farm_id=farm, now=NOW)
        return first, await conn.fetchval("SELECT state FROM irrigation_jobs WHERE id=$1", job)

    assert run(scenario) == ("done", "done")


def test_given_another_pass_holding_the_farm_lock_then_the_computation_waits_for_it():
    async def scenario(conn):
        import asyncpg

        from tests._f3 import DSN

        farm, parcel = await seed_world(conn)
        other = await asyncpg.connect(DSN)
        try:
            tx = other.transaction()
            await tx.start()
            await other.execute("SELECT pg_advisory_xact_lock(hashtextextended($1, 0))", f"irrigation:{farm}")
            task = asyncio.ensure_future(compute_irrigation_plans({}, farm_id=farm, now=NOW))
            done, _ = await asyncio.wait({task}, timeout=1.0)
            blocked = not done and await plan(conn, parcel) is None
            await tx.commit()
            await asyncio.wait_for(task, timeout=30)
            return blocked, await plan(conn, parcel)
        finally:
            await other.close()

    blocked, row = run(scenario)
    assert blocked is True and row is not None


def test_given_an_advice_that_changes_then_recompute_status_is_queued_once_and_not_when_it_is_unchanged():
    async def scenario(conn):
        farm, parcel = await seed_world(conn)
        redis = SpyRedis()
        await compute_irrigation_plans({"redis": redis}, farm_id=farm, now=NOW)
        changed = list(redis.jobs)
        await compute_irrigation_plans({"redis": redis}, farm_id=farm, now=NOW)
        return farm, changed, list(redis.jobs)

    farm, changed, after_replay = run(scenario)
    assert [j[0] for j in changed] == ["recompute_status"] and str(changed[0][1]["farm_id"]) == str(farm)
    assert after_replay == changed


def test_given_a_weather_refresh_then_a_computation_is_scheduled_for_the_farms_of_the_cell():
    import tasks.refresh_weather as rw
    from tests._f3 import day, seed_farm

    class Gateway:
        def configured(self):
            return True

        def fetch(self, *, lat_r, lon_r):
            return {"availability": "ok", "days": [day(i) for i in range(8)]}

    async def scenario(conn):
        lat_r, lon_r = 21.0 + uuid.uuid4().int % 300 / 10, -2.0 - uuid.uuid4().int % 100 / 10
        farm = await seed_farm(conn, lat=lat_r, lon=lon_r)
        redis = SpyRedis()
        await rw.refresh_weather({"gateway": Gateway(), "redis": redis}, dt.datetime.now(dt.UTC))  # clock-allow: F3 signature takes an instant
        return farm, redis.jobs

    farm, jobs = run(scenario)
    assert any(n == "compute_irrigation_plans" and str(k.get("farm_id")) == str(farm) for n, k in jobs)
