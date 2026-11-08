"""T055 - R3-A2, SC-004: a scene under 80 percent clear is logged as rejected_cloud and never published; only a public tile id and dates leave."""
import datetime as dt
import random
import string
import uuid

from tasks.ingest_imagery import ingest_imagery, publish_scene_stats
from tests._f3 import TODAY, run, seed_farm, seed_parcel


def _tile():
    return f"{random.randint(10, 60)}{''.join(random.choices(string.ascii_uppercase.replace('I', '').replace('O', ''), k=3))}"


async def _scene(conn, tile, on):
    sid = uuid.uuid4()
    await conn.execute("INSERT INTO imagery_tiles (tile_id, last_ingested_on) VALUES ($1,$2) ON CONFLICT DO NOTHING", tile, on)
    await conn.execute("INSERT INTO imagery_scenes (id, tile_id, acquired_on, cloud_pct_scene, raster_key, ingested_at) VALUES ($1,$2,$3,10,$4,now())", sid, tile, on, f"rasters/{sid}")
    return sid


def _stats(clear):
    return {"vigor_mean": 0.61, "plant_moisture_mean": 0.33, "clear_pct": clear}


class SpyImagery:
    def __init__(self, scenes=None, configured=True):
        self._configured, self.calls, self._scenes = configured, [], scenes or []

    def configured(self):
        return self._configured

    def scenes(self, *, mgrs, date_from, date_to):
        self.calls.append({"mgrs": mgrs, "date_from": date_from, "date_to": date_to})
        return {"availability": "ok", "scenes": self._scenes}


def test_given_a_scene_with_79_9_percent_clear_when_publishing_then_no_point_is_written_and_the_scene_is_logged_rejected_cloud():
    async def scenario(conn):
        farm = await seed_farm(conn)
        parcel = await seed_parcel(conn, farm)
        scene = await _scene(conn, _tile(), TODAY - dt.timedelta(days=3))
        outcome = await publish_scene_stats(conn, farm_id=farm, parcel_id=parcel, scene_id=scene, acquired_on=TODAY - dt.timedelta(days=3), stats=_stats(79.9))
        points = await conn.fetchval("SELECT count(*) FROM parcel_vigor_points WHERE parcel_id = $1", parcel)
        logged = await conn.fetchval("SELECT outcome FROM parcel_scene_log WHERE parcel_id = $1 AND scene_id = $2", parcel, scene)
        return outcome, points, logged

    assert run(scenario) == ("rejected_cloud", 0, "rejected_cloud")


def test_given_a_scene_with_exactly_80_percent_clear_when_publishing_then_the_point_is_written_with_its_values_and_the_scene_is_logged_ok():
    async def scenario(conn):
        farm = await seed_farm(conn)
        parcel = await seed_parcel(conn, farm)
        scene = await _scene(conn, _tile(), TODAY - dt.timedelta(days=3))
        outcome = await publish_scene_stats(conn, farm_id=farm, parcel_id=parcel, scene_id=scene, acquired_on=TODAY - dt.timedelta(days=3), stats=_stats(80.0))
        row = await conn.fetchrow("SELECT vigor_mean, plant_moisture_mean, clear_pct, valid FROM parcel_vigor_points WHERE parcel_id = $1", parcel)
        return outcome, float(row["vigor_mean"]), float(row["plant_moisture_mean"]), float(row["clear_pct"]), row["valid"]

    assert run(scenario) == ("ok", 0.61, 0.33, 80.0, True)


def test_given_the_same_scene_published_twice_then_there_is_a_single_point():
    async def scenario(conn):
        farm = await seed_farm(conn)
        parcel = await seed_parcel(conn, farm)
        scene = await _scene(conn, _tile(), TODAY - dt.timedelta(days=3))
        for _ in range(2):
            await publish_scene_stats(conn, farm_id=farm, parcel_id=parcel, scene_id=scene, acquired_on=TODAY - dt.timedelta(days=3), stats=_stats(95))
        return await conn.fetchval("SELECT count(*) FROM parcel_vigor_points WHERE parcel_id = $1", parcel)

    assert run(scenario) == 1


def test_given_a_scene_without_any_clear_pixel_values_when_publishing_then_nothing_is_invented_and_it_is_rejected():
    async def scenario(conn):
        farm = await seed_farm(conn)
        parcel = await seed_parcel(conn, farm)
        scene = await _scene(conn, _tile(), TODAY - dt.timedelta(days=3))
        out = await publish_scene_stats(conn, farm_id=farm, parcel_id=parcel, scene_id=scene, acquired_on=TODAY - dt.timedelta(days=3),
                                        stats={"vigor_mean": None, "plant_moisture_mean": None, "clear_pct": 0.0})
        return out, await conn.fetchval("SELECT count(*) FROM parcel_vigor_points WHERE parcel_id = $1", parcel)

    assert run(scenario) == ("rejected_cloud", 0)


def test_given_a_tile_and_dates_when_ingesting_then_the_gateway_receives_only_the_public_tile_id_and_the_dates():
    tile = _tile()
    spy = SpyImagery([{"acquired_on": (TODAY - dt.timedelta(days=4)).isoformat(), "cloud_pct_scene": 12}])

    async def scenario(conn):
        await ingest_imagery({"gateway": spy}, tile_id=tile, date_from=TODAY - dt.timedelta(days=10), date_to=TODAY)
        return await conn.fetchval("SELECT count(*) FROM imagery_scenes WHERE tile_id = $1", tile)

    assert run(scenario) == 1
    assert spy.calls == [{"mgrs": tile, "date_from": (TODAY - dt.timedelta(days=10)).isoformat(), "date_to": TODAY.isoformat()}]


def test_given_a_scene_already_ingested_when_ingesting_again_then_it_is_not_duplicated_and_not_downloaded_twice():
    tile = _tile()
    scenes = [{"acquired_on": (TODAY - dt.timedelta(days=4)).isoformat(), "cloud_pct_scene": 12}]
    spy = SpyImagery(scenes)

    async def scenario(conn):
        for _ in range(2):
            await ingest_imagery({"gateway": spy}, tile_id=tile, date_from=TODAY - dt.timedelta(days=10), date_to=TODAY)
        return await conn.fetchval("SELECT count(*) FROM imagery_scenes WHERE tile_id = $1", tile)

    assert run(scenario) == 1


def test_given_no_configured_gateway_when_ingesting_then_no_scene_and_no_point_are_created():
    tile = _tile()
    off = SpyImagery(configured=False)

    async def scenario(conn):
        await ingest_imagery({"gateway": off}, tile_id=tile, date_from=TODAY - dt.timedelta(days=10), date_to=TODAY)
        return await conn.fetchval("SELECT count(*) FROM imagery_scenes WHERE tile_id = $1", tile)

    assert run(scenario) == 0 and off.calls == []
