"""T055 - R3-A1, SC-002: the initial history covers the last 12 months from scenes already ingested, one active job per parcel, duration measured."""
import datetime as dt
import random
import string
import uuid

from tasks.backfill_parcel_vigor import backfill_parcel_vigor, enqueue_backfill
from tests._f3 import TODAY, run, seed_farm, seed_parcel

NOW = dt.datetime.now(dt.UTC)


def _tile():
    return f"{random.randint(10, 60)}{''.join(random.choices('ABCDEFGHJKLMNPQRSTUVWXYZ', k=3))}"


async def _scene(conn, tile, days_ago):
    sid, on = uuid.uuid4(), TODAY - dt.timedelta(days=days_ago)
    await conn.execute("INSERT INTO imagery_tiles (tile_id, last_ingested_on) VALUES ($1,$2) ON CONFLICT DO NOTHING", tile, on)
    await conn.execute("INSERT INTO imagery_scenes (id, tile_id, acquired_on, cloud_pct_scene, raster_key, ingested_at) VALUES ($1,$2,$3,10,$4,now())", sid, tile, on, f"rasters/{sid}")
    return sid


def _ctx(tile, clear_by_scene):
    return {"tiles_for": lambda parcel: [tile],
            "stats_for": lambda scene, parcel: {"vigor_mean": 0.5, "plant_moisture_mean": 0.3, "clear_pct": clear_by_scene[scene]}}


def test_given_scenes_of_the_last_12_months_when_backfilling_then_only_valid_ones_in_the_window_are_published_and_the_job_duration_is_measured():
    tile = _tile()

    async def scenario(conn):
        farm = await seed_farm(conn)
        parcel = await seed_parcel(conn, farm)
        recent, cloudy, old = await _scene(conn, tile, 20), await _scene(conn, tile, 60), await _scene(conn, tile, 500)
        job = await enqueue_backfill(conn, farm_id=farm, parcel_id=parcel)
        await backfill_parcel_vigor(_ctx(tile, {recent: 95, cloudy: 70, old: 99}), farm_id=farm, parcel_id=parcel, now=NOW)
        pts = {r["scene_id"] for r in await conn.fetch("SELECT scene_id FROM parcel_vigor_points WHERE parcel_id = $1", parcel)}
        j = await conn.fetchrow("SELECT state, started_at, finished_at, duration_s FROM monitoring_jobs WHERE id = $1", job)
        return pts, {recent}, dict(j)

    pts, expected, job = run(scenario)
    assert pts == expected
    assert job["state"] == "done" and job["started_at"] and job["finished_at"] and job["duration_s"] is not None and float(job["duration_s"]) >= 0


def test_given_an_active_backfill_when_enqueueing_again_then_the_same_job_is_returned_and_only_one_is_active():
    async def scenario(conn):
        farm = await seed_farm(conn)
        parcel = await seed_parcel(conn, farm)
        first = await enqueue_backfill(conn, farm_id=farm, parcel_id=parcel)
        second = await enqueue_backfill(conn, farm_id=farm, parcel_id=parcel)
        active = await conn.fetchval("SELECT count(*) FROM monitoring_jobs WHERE parcel_id = $1 AND kind = 'backfill' AND state IN ('queued','running')", parcel)
        return first, second, active

    first, second, active = run(scenario)
    assert first == second and active == 1


def test_given_a_backfill_run_twice_when_scenes_are_unchanged_then_points_are_not_duplicated():
    tile = _tile()

    async def scenario(conn):
        farm = await seed_farm(conn)
        parcel = await seed_parcel(conn, farm)
        s = await _scene(conn, tile, 10)
        await enqueue_backfill(conn, farm_id=farm, parcel_id=parcel)
        await backfill_parcel_vigor(_ctx(tile, {s: 90}), farm_id=farm, parcel_id=parcel, now=NOW)
        await enqueue_backfill(conn, farm_id=farm, parcel_id=parcel)
        await backfill_parcel_vigor(_ctx(tile, {s: 90}), farm_id=farm, parcel_id=parcel, now=NOW)
        return await conn.fetchval("SELECT count(*) FROM parcel_vigor_points WHERE parcel_id = $1", parcel)

    assert run(scenario) == 1


def test_given_an_archived_parcel_when_backfilling_then_nothing_is_published():
    tile = _tile()

    async def scenario(conn):
        farm = await seed_farm(conn)
        parcel = await seed_parcel(conn, farm, archived=True)
        s = await _scene(conn, tile, 10)
        await backfill_parcel_vigor(_ctx(tile, {s: 90}), farm_id=farm, parcel_id=parcel, now=NOW)
        return await conn.fetchval("SELECT count(*) FROM parcel_vigor_points WHERE parcel_id = $1", parcel)

    assert run(scenario) == 0


def test_given_a_stats_failure_when_backfilling_then_the_job_ends_failed_and_no_value_is_invented():
    tile = _tile()

    async def scenario(conn):
        farm = await seed_farm(conn)
        parcel = await seed_parcel(conn, farm)
        await _scene(conn, tile, 10)
        job = await enqueue_backfill(conn, farm_id=farm, parcel_id=parcel)

        def boom(scene, parcel_id):
            raise RuntimeError("raster unreadable")

        await backfill_parcel_vigor({"tiles_for": lambda p: [tile], "stats_for": boom}, farm_id=farm, parcel_id=parcel, now=NOW)
        return await conn.fetchval("SELECT state FROM monitoring_jobs WHERE id = $1", job), await conn.fetchval("SELECT count(*) FROM parcel_vigor_points WHERE parcel_id = $1", parcel)

    assert run(scenario) == ("failed", 0)
