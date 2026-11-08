"""Defect 3 - the backfill reads parcels through the shared visibility predicate like every other F3 path: an archived parcel or a deleted farm
is never read (no raster access) and its job does not stay queued or running."""
import datetime as dt
import random
import uuid
from pathlib import Path

from tasks.backfill_parcel_vigor import backfill_parcel_vigor, enqueue_backfill
from tests._f3 import TODAY, run, seed_farm, seed_parcel

NOW = dt.datetime.now(dt.UTC)
SOURCE = (Path(__file__).resolve().parents[1] / "tasks" / "backfill_parcel_vigor.py").read_text(encoding="utf-8")


class Spy:
    def __init__(self):
        self.tiles, self.stats = [], []

    def ctx(self, tile):
        return {"tiles_for": lambda parcel: self.tiles.append(parcel) or [tile],
                "stats_for": lambda scene, parcel: self.stats.append(parcel) or {"vigor_mean": 0.5, "plant_moisture_mean": 0.3, "clear_pct": 95}}


async def _scene(conn, tile):
    sid = uuid.uuid4()
    await conn.execute("INSERT INTO imagery_tiles (tile_id, last_ingested_on) VALUES ($1,$2) ON CONFLICT DO NOTHING", tile, TODAY)
    await conn.execute("INSERT INTO imagery_scenes (id, tile_id, acquired_on, cloud_pct_scene, raster_key, ingested_at) VALUES ($1,$2,$3,10,$4,now())", sid, tile, TODAY - dt.timedelta(days=5), f"rasters/{sid}")


def _tile():
    return f"{random.randint(10, 60)}{''.join(random.choices('ABCDEFGHJKLMNPQRSTUVWXYZ', k=3))}"


async def _state(conn, job):
    return await conn.fetchval("SELECT state FROM monitoring_jobs WHERE id = $1", job)


def test_given_the_backfill_source_then_it_uses_the_shared_visibility_predicate_and_never_scans_raw_parcels():
    assert "VISIBLE_PARCELS_SQL" in SOURCE and "access_sql" in SOURCE
    import re
    assert not re.search(r"FROM\s+parcels\b", SOURCE, re.IGNORECASE)


def test_given_a_parcel_archived_after_the_job_was_queued_when_backfilling_then_no_raster_is_read_and_the_job_does_not_stay_active():
    tile, spy = _tile(), Spy()

    async def scenario(conn):
        farm = await seed_farm(conn)
        parcel = await seed_parcel(conn, farm)
        await _scene(conn, tile)
        job = await enqueue_backfill(conn, farm_id=farm, parcel_id=parcel)
        await conn.execute("UPDATE parcels SET archived_at = now() WHERE id = $1", parcel)
        result = await backfill_parcel_vigor(spy.ctx(tile), farm_id=farm, parcel_id=parcel, now=NOW)
        return result, await _state(conn, job), await conn.fetchval("SELECT count(*) FROM parcel_vigor_points WHERE parcel_id = $1", parcel)

    result, state, points = run(scenario)
    assert result in ("skipped", "failed") and state not in ("queued", "running") and points == 0
    assert spy.tiles == [] and spy.stats == []


def test_given_a_farm_deleted_after_the_job_was_queued_when_backfilling_then_no_raster_is_read_and_the_job_does_not_stay_active():
    tile, spy = _tile(), Spy()

    async def scenario(conn):
        farm = await seed_farm(conn)
        parcel = await seed_parcel(conn, farm)
        await _scene(conn, tile)
        job = await enqueue_backfill(conn, farm_id=farm, parcel_id=parcel)
        await conn.execute("UPDATE farms SET deleted_at = now() WHERE id = $1", farm)
        result = await backfill_parcel_vigor(spy.ctx(tile), farm_id=farm, parcel_id=parcel, now=NOW)
        return result, await _state(conn, job), await conn.fetchval("SELECT count(*) FROM parcel_vigor_points WHERE parcel_id = $1", parcel)

    result, state, points = run(scenario)
    assert result in ("skipped", "failed") and state not in ("queued", "running") and points == 0
    assert spy.tiles == [] and spy.stats == []


def test_given_a_visible_parcel_when_backfilling_then_the_rasters_are_read_and_the_job_is_done():
    tile, spy = _tile(), Spy()

    async def scenario(conn):
        farm = await seed_farm(conn)
        parcel = await seed_parcel(conn, farm)
        await _scene(conn, tile)
        job = await enqueue_backfill(conn, farm_id=farm, parcel_id=parcel)
        await backfill_parcel_vigor(spy.ctx(tile), farm_id=farm, parcel_id=parcel, now=NOW)
        return await _state(conn, job)

    assert run(scenario) == "done" and spy.tiles
