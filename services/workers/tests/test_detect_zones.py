"""T062 - R4-A1: after a new scene, an abnormal drop is delimited as an open zone (quotas: 5 open per parcel, 200 per farm, outline <= 200 vertices).

Thresholds are injected through `ctx["params"]` (agronomic reference values; never seeded in monitoring_params) and the drop grid through
`ctx["grid_for"](parcel_id)` (the raster reading seam). Without thresholds nothing is detected.
"""
import datetime as dt
import uuid

import numpy as np

from tasks.detect_zones import detect_zones
from tests._f3 import run, seed_farm, seed_parcel

BOUNDS = (-7.60, 33.57, -7.598, 33.572)
PARAMS = {"anomaly_drop": 0.15, "anomaly_min_pixels": 20, "anomaly_resolved_vigor": 0.5}
NOW = dt.datetime.now(dt.UTC)


def _grid(blocks, size=40):
    drop = np.zeros((size, size))
    for (r0, r1, c0, c1), score in blocks:
        drop[r0:r1, c0:c1] = score
    return {"drop": drop, "valid": np.ones((size, size), dtype=bool), "bounds": BOUNDS}


def _ctx(grids, params=PARAMS):
    c = {"grid_for": lambda parcel: grids.get(parcel)}
    if params is not None:
        c["params"] = params
    return c


async def _zones(conn, farm):
    return [dict(r) for r in await conn.fetch(
        "SELECT id, parcel_id, status, reason_key, drop_score, area_ha, detected_on, ST_GeometryType(geometry) AS gt, ST_NPoints(geometry) AS n,"
        " ST_GeometryType(centroid) AS ct FROM attention_zones WHERE farm_id = $1", farm)]


def test_given_a_new_scene_with_a_dropping_block_when_detecting_then_an_open_zone_is_delimited_with_outline_and_centroid():
    async def scenario(conn):
        farm = await seed_farm(conn)
        parcel = await seed_parcel(conn, farm)
        await detect_zones(_ctx({parcel: _grid([((2, 8, 2, 8), 0.3)])}), NOW, farm_id=farm)
        return await _zones(conn, farm), parcel

    (z,), parcel = run(scenario)
    assert (z["parcel_id"], z["status"], z["gt"], z["ct"]) == (parcel, "open", "ST_Polygon", "ST_Point")
    assert z["reason_key"] and float(z["drop_score"]) == 0.3 and float(z["area_ha"]) > 0 and z["detected_on"] == NOW.date()


def test_given_no_reference_threshold_when_detecting_then_nothing_is_detected_and_no_default_is_assumed():
    async def scenario(conn):
        farm = await seed_farm(conn)
        parcel = await seed_parcel(conn, farm)
        await detect_zones(_ctx({parcel: _grid([((2, 8, 2, 8), 0.9)])}, params=None), NOW, farm_id=farm)
        return await _zones(conn, farm)

    assert run(scenario) == []


def test_given_the_same_scene_detected_twice_when_detecting_then_the_zone_is_not_duplicated():
    async def scenario(conn):
        farm = await seed_farm(conn)
        parcel = await seed_parcel(conn, farm)
        ctx = _ctx({parcel: _grid([((2, 8, 2, 8), 0.3)])})
        await detect_zones(ctx, NOW, farm_id=farm)
        await detect_zones(ctx, NOW + dt.timedelta(hours=6), farm_id=farm)
        return await _zones(conn, farm)

    assert len(run(scenario)) == 1


def test_given_seven_separate_anomalies_on_a_parcel_when_detecting_then_at_most_5_open_zones_are_kept_the_strongest_first():
    async def scenario(conn):
        farm = await seed_farm(conn)
        parcel = await seed_parcel(conn, farm)
        blocks = [((r, r + 5, c, c + 5), 0.2 + 0.02 * i) for i, (r, c) in enumerate([(0, 0), (0, 10), (0, 20), (10, 0), (10, 10), (10, 20), (20, 0)])]
        await detect_zones(_ctx({parcel: _grid(blocks)}), NOW, farm_id=farm)
        return await _zones(conn, farm)

    zones = run(scenario)
    assert len(zones) == 5 and min(float(z["drop_score"]) for z in zones) >= 0.24


def test_given_a_farm_with_198_open_zones_when_detecting_three_more_then_the_farm_stops_at_200():
    async def scenario(conn):
        farm = await seed_farm(conn)
        parcels = [await seed_parcel(conn, farm) for _ in range(40)]
        for i in range(198):
            await conn.execute(
                "INSERT INTO attention_zones (id, farm_id, parcel_id, geometry, centroid, detected_on, status, reason_key)"
                " VALUES ($1,$2,$3,ST_GeomFromText('POLYGON((-7.6 33.57,-7.599 33.57,-7.599 33.571,-7.6 33.57))',4326),ST_GeomFromText('POINT(-7.5995 33.5705)',4326),$4,'resolved','zone.fixture')",
                uuid.uuid4(), farm, parcels[i % 40], NOW.date())
        await conn.execute("UPDATE attention_zones SET status = 'open' WHERE farm_id = $1", farm)
        fresh = {p: _grid([((2, 8, 2, 8), 0.3)]) for p in parcels[:3]}
        await detect_zones(_ctx(fresh), NOW, farm_id=farm)
        return await conn.fetchval("SELECT count(*) FROM attention_zones WHERE farm_id = $1 AND status = 'open'", farm)

    assert run(scenario) <= 200


def test_given_an_archived_parcel_when_detecting_then_no_zone_is_created():
    async def scenario(conn):
        farm = await seed_farm(conn)
        parcel = await seed_parcel(conn, farm, archived=True)
        await detect_zones(_ctx({parcel: _grid([((2, 8, 2, 8), 0.3)])}), NOW, farm_id=farm)
        return await _zones(conn, farm)

    assert run(scenario) == []


def test_given_a_very_irregular_anomaly_when_detecting_then_the_stored_outline_has_at_most_200_vertices():
    async def scenario(conn):
        farm = await seed_farm(conn)
        parcel = await seed_parcel(conn, farm)
        drop = np.zeros((80, 80))
        for r in range(2, 78):
            drop[r, 2: 40 + (r % 2) * 30] = 0.3  # saw-tooth right edge: hundreds of corners
        grid = {"drop": drop, "valid": np.ones((80, 80), dtype=bool), "bounds": BOUNDS}
        await detect_zones(_ctx({parcel: grid}), NOW, farm_id=farm)
        return await _zones(conn, farm)

    zones = run(scenario)
    assert zones and all(z["n"] <= 200 for z in zones)


def test_given_a_zone_whose_vigor_is_back_above_the_threshold_on_two_valid_scenes_when_detecting_then_it_is_resolved_and_a_visited_one_too():
    async def scenario(conn):
        farm = await seed_farm(conn)
        parcel = await seed_parcel(conn, farm)
        ids = []
        for status in ("open", "visited"):
            zid = uuid.uuid4()
            ids.append(zid)
            await conn.execute(
                "INSERT INTO attention_zones (id, farm_id, parcel_id, geometry, centroid, detected_on, status, reason_key)"
                " VALUES ($1,$2,$3,ST_GeomFromText('POLYGON((-7.6 33.57,-7.599 33.57,-7.599 33.571,-7.6 33.57))',4326),ST_GeomFromText('POINT(-7.5995 33.5705)',4326),$4,$5,'zone.fixture')",
                zid, farm, parcel, NOW.date(), status)
        for d in (10, 5):
            scene = uuid.uuid4()
            on = NOW.date() - dt.timedelta(days=d)
            await conn.execute("INSERT INTO imagery_tiles (tile_id, last_ingested_on) VALUES ('31SBU', $1) ON CONFLICT DO NOTHING", on)
            await conn.execute("INSERT INTO imagery_scenes (id, tile_id, acquired_on, cloud_pct_scene, raster_key) VALUES ($1,'31SBU',$2,5,$3)", scene, on, f"rasters/{scene}")
            await conn.execute("INSERT INTO parcel_vigor_points (id, farm_id, parcel_id, scene_id, acquired_on, vigor_mean, plant_moisture_mean, clear_pct) VALUES ($1,$2,$3,$4,$5,0.7,0.4,95)",
                               uuid.uuid4(), farm, parcel, scene, on)
        await detect_zones(_ctx({}), NOW, farm_id=farm)
        return [r["status"] for r in await conn.fetch("SELECT status FROM attention_zones WHERE farm_id = $1", farm)]

    assert run(scenario) == ["resolved", "resolved"]


def test_given_the_worker_settings_then_detection_is_registered_and_scheduled():
    import worker

    assert detect_zones in worker.WorkerSettings.functions
    assert detect_zones in [c.coroutine for c in worker.WorkerSettings.cron_jobs]
