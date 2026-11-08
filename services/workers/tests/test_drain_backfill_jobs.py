"""Defect 1 (decisions.md, points ouverts) - queued `backfill` jobs are consumed: a periodic drain moves them queued -> running -> done|failed,
so `processing` falls back to false. Reprocess jobs are not its business."""
import datetime as dt
import random
import uuid

import worker
from tasks.backfill_parcel_vigor import enqueue_backfill
from tasks.drain_backfill_jobs import drain_backfill_jobs
from tests._f3 import TODAY, run, seed_farm, seed_parcel

NOW = dt.datetime.now(dt.UTC)


def _tile():
    return f"{random.randint(10, 60)}{''.join(random.choices('ABCDEFGHJKLMNPQRSTUVWXYZ', k=3))}"


async def _scene(conn, tile, days_ago):
    sid, on = uuid.uuid4(), TODAY - dt.timedelta(days=days_ago)
    await conn.execute("INSERT INTO imagery_tiles (tile_id, last_ingested_on) VALUES ($1,$2) ON CONFLICT DO NOTHING", tile, on)
    await conn.execute("INSERT INTO imagery_scenes (id, tile_id, acquired_on, cloud_pct_scene, raster_key, ingested_at) VALUES ($1,$2,$3,10,$4,now())", sid, tile, on, f"rasters/{sid}")
    return sid


def _ctx(tile, calls=None):
    def stats(scene, parcel):
        if calls is not None:
            calls.append(parcel)
        return {"vigor_mean": 0.5, "plant_moisture_mean": 0.3, "clear_pct": 95}

    return {"tiles_for": lambda parcel: [tile], "stats_for": stats}


async def _job(conn, job):
    return dict(await conn.fetchrow("SELECT state, started_at, finished_at, duration_s FROM monitoring_jobs WHERE id = $1", job))


async def _processing(conn, parcel):
    return await conn.fetchval("SELECT count(*) FROM monitoring_jobs WHERE parcel_id = $1 AND state IN ('queued','running')", parcel) > 0


def test_given_a_queued_backfill_and_a_raster_reader_when_draining_then_the_job_is_done_the_history_is_published_and_the_parcel_is_not_processing_anymore():
    tile = _tile()

    async def scenario(conn):
        farm = await seed_farm(conn)
        parcel = await seed_parcel(conn, farm)
        await _scene(conn, tile, 20)
        job = await enqueue_backfill(conn, farm_id=farm, parcel_id=parcel)
        before = await _processing(conn, parcel)
        n = await drain_backfill_jobs(_ctx(tile), NOW, farm_id=farm)
        return before, n, await _job(conn, job), await _processing(conn, parcel), await conn.fetchval("SELECT count(*) FROM parcel_vigor_points WHERE parcel_id = $1", parcel)

    before, n, job, after, points = run(scenario)
    assert before is True and n == 1 and after is False and points == 1
    assert job["state"] == "done" and job["started_at"] and job["finished_at"] and job["duration_s"] is not None


def test_given_a_queued_backfill_and_no_raster_reader_when_draining_then_the_job_fails_with_no_value_invented_and_the_parcel_is_not_processing_anymore():
    async def scenario(conn):
        farm = await seed_farm(conn)
        parcel = await seed_parcel(conn, farm)
        job = await enqueue_backfill(conn, farm_id=farm, parcel_id=parcel)
        await drain_backfill_jobs({}, NOW, farm_id=farm)
        return await _job(conn, job), await _processing(conn, parcel), await conn.fetchval("SELECT count(*) FROM parcel_vigor_points WHERE parcel_id = $1", parcel)

    job, processing, points = run(scenario)
    assert job["state"] == "failed" and job["finished_at"] is not None and processing is False and points == 0


def test_given_several_queued_backfills_when_draining_then_each_is_handled_and_a_failing_one_does_not_block_the_others():
    tile = _tile()

    async def scenario(conn):
        farm = await seed_farm(conn)
        good, bad = await seed_parcel(conn, farm), await seed_parcel(conn, farm)
        await _scene(conn, tile, 15)
        jg, jb = await enqueue_backfill(conn, farm_id=farm, parcel_id=good), await enqueue_backfill(conn, farm_id=farm, parcel_id=bad)

        def stats(scene, parcel):
            if parcel == bad:
                raise RuntimeError("unreadable raster")
            return {"vigor_mean": 0.5, "plant_moisture_mean": 0.3, "clear_pct": 95}

        n = await drain_backfill_jobs({"tiles_for": lambda p: [tile], "stats_for": stats}, NOW, farm_id=farm)
        return n, (await _job(conn, jg))["state"], (await _job(conn, jb))["state"]

    assert run(scenario) == (2, "done", "failed")


def test_given_a_reprocess_job_when_draining_then_it_is_left_queued():
    tile = _tile()

    async def scenario(conn):
        farm = await seed_farm(conn)
        parcel = await seed_parcel(conn, farm)
        job = uuid.uuid4()
        await conn.execute("INSERT INTO monitoring_jobs (id, farm_id, parcel_id, kind, state) VALUES ($1,$2,$3,'reprocess','queued')", job, farm, parcel)
        n = await drain_backfill_jobs(_ctx(tile), NOW, farm_id=farm)
        return n, (await _job(conn, job))["state"]

    assert run(scenario) == (0, "queued")


def test_given_a_farm_id_when_draining_then_the_jobs_of_other_farms_are_not_touched():
    tile = _tile()

    async def scenario(conn):
        farm, other = await seed_farm(conn), await seed_farm(conn)
        parcel, other_parcel = await seed_parcel(conn, farm), await seed_parcel(conn, other)
        await enqueue_backfill(conn, farm_id=farm, parcel_id=parcel)
        foreign = await enqueue_backfill(conn, farm_id=other, parcel_id=other_parcel)
        await drain_backfill_jobs(_ctx(tile), NOW, farm_id=farm)
        return (await _job(conn, foreign))["state"]

    assert run(scenario) == "queued"


def test_given_a_drain_already_done_when_draining_again_then_nothing_is_reprocessed():
    tile = _tile()
    calls = []

    async def scenario(conn):
        farm = await seed_farm(conn)
        parcel = await seed_parcel(conn, farm)
        await _scene(conn, tile, 10)
        await enqueue_backfill(conn, farm_id=farm, parcel_id=parcel)
        first = await drain_backfill_jobs(_ctx(tile, calls), NOW, farm_id=farm)
        seen = len(calls)
        again = await drain_backfill_jobs(_ctx(tile, calls), NOW, farm_id=farm)
        return first, again, seen, len(calls)

    assert run(scenario) == (1, 0, 1, 1)


def test_given_the_worker_settings_then_the_drain_is_a_registered_function_and_a_periodic_job():
    assert drain_backfill_jobs in worker.WorkerSettings.functions
    assert drain_backfill_jobs in [c.coroutine for c in worker.WorkerSettings.cron_jobs]
