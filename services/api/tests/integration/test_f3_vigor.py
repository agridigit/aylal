"""T055 - R3-A1..A4: published vigor never comes from a rejected cloudy scene; the last valid image stays with its date; plain-language labels; initial history job."""
import datetime as dt
import uuid

from tests.helpers import auth, sql
from tests.integration._f2 import square
from tests.integration._f3 import call, seed_scene, world3  # noqa: F401

TODAY = dt.date.today()


def _cloudy(farm, parcel, on, clear=70):
    scene = uuid.uuid4()
    sql("INSERT INTO imagery_tiles (tile_id, last_ingested_on) VALUES ('31SBU', $1) ON CONFLICT DO NOTHING", on)
    sql("INSERT INTO imagery_scenes (id, tile_id, acquired_on, cloud_pct_scene, raster_key, ingested_at) VALUES ($1,'31SBU',$2,60,$3,now())", scene, on, f"rasters/{scene}")
    sql("INSERT INTO parcel_vigor_points (id, farm_id, parcel_id, scene_id, acquired_on, vigor_mean, plant_moisture_mean, clear_pct, reliability)"
        " VALUES ($1,$2,$3,$4,$5,0.2,0.2,$6,'ok')", uuid.uuid4(), farm, parcel, scene, on, clear)
    return scene


def _vigor(client, token_for, w, parcel=None, who="owner", query=""):
    return call(client, token_for(w[who]), "GET", f"/v1/farms/{w['farm_a']}/parcels/{parcel or w['a1']}/vigor{query}")


def test_given_a_recent_cloudy_scene_when_reading_the_vigor_then_it_is_never_published_and_the_last_valid_image_keeps_its_date(client, token_for, world3):
    w = world3
    p = w["p"][8]
    older = TODAY - dt.timedelta(days=12)
    _, map_id = seed_scene(w["farm_a"], p, acquired_on=older)
    _cloudy(w["farm_a"], p, TODAY - dt.timedelta(days=2), clear=70)
    b = _vigor(client, token_for, w, parcel=p).json()
    assert [pt["acquired_on"] for pt in b["points"]] == [older.isoformat()]
    assert all(pt["clear_pct"] >= 80 for pt in b["points"])
    assert b["last_valid_map"] == {"map_id": str(map_id), "acquired_on": older.isoformat()}


def test_given_a_scene_at_exactly_80_percent_clear_when_reading_then_it_is_published_and_79_9_is_not(client, token_for, world3):
    w = world3
    p = w["p"][7]
    _cloudy(w["farm_a"], p, TODAY - dt.timedelta(days=20), clear=80)
    _cloudy(w["farm_a"], p, TODAY - dt.timedelta(days=10), clear=79.9)
    pts = _vigor(client, token_for, w, parcel=p).json()["points"]
    assert [pt["clear_pct"] for pt in pts] == [80]


def test_given_the_vigor_series_then_values_are_named_vigor_and_plant_moisture_and_never_ndvi_or_ndmi(client, token_for, world3):
    w = world3
    seed_scene(w["farm_a"], w["a1"])
    r = _vigor(client, token_for, w)
    text = r.text.lower()
    assert "ndvi" not in text and "ndmi" not in text
    assert {"vigor", "plant_moisture"} <= set(r.json()["points"][0])


def test_given_a_greenhouse_or_small_parcel_when_reading_then_imagery_is_flagged_low_reliability(client, token_for, world3):
    w = world3
    sql("UPDATE parcels SET greenhouse = true WHERE id = $1", w["p"][9])
    seed_scene(w["farm_a"], w["p"][9])
    assert _vigor(client, token_for, w, parcel=w["p"][9]).json()["reliability"] == "low"


def test_given_a_series_window_over_24_months_when_reading_then_it_is_refused(client, token_for, world3):
    w = world3
    start = (TODAY - dt.timedelta(days=800)).isoformat()
    r = _vigor(client, token_for, w, query=f"?from={start}&to={TODAY.isoformat()}")
    assert r.status_code in (413, 422)


def test_given_a_parcel_just_created_when_the_creation_completes_then_one_initial_history_job_is_queued_and_the_series_says_processing(client, token_for, world3):
    w = world3
    r = client.post(f"/v1/farms/{w['farm_a']}/fields", headers=auth(token_for(w["owner"])), json={"name": "Nouvelle", "geometry": square(-7.45)})
    assert r.status_code == 201, r.text
    parcel = r.json()["id"]
    jobs = sql("SELECT kind, state FROM monitoring_jobs WHERE parcel_id = $1", uuid.UUID(parcel))
    assert [(j["kind"], j["state"]) for j in jobs] == [("backfill", "queued")]
    b = call(client, token_for(w["owner"]), "GET", f"/v1/farms/{w['farm_a']}/parcels/{parcel}/vigor").json()
    assert b["processing"] is True and b["points"] == []


def test_given_a_worker_when_reading_the_vigor_of_a_parcel_not_assigned_then_404_identical(client, token_for, world3):
    w = world3
    r = _vigor(client, token_for, w, parcel=w["hidden"], who="worker")
    assert r.status_code == 404 and r.json() == {"detail": "not_found"}


def test_given_a_worker_when_requesting_a_reprocessing_then_403_and_no_job_is_created(client, token_for, world3):
    w = world3
    before = sql("SELECT count(*) FROM monitoring_jobs WHERE parcel_id = $1", w["a1"])[0][0]
    assert call(client, token_for(w["worker"]), "POST", f"/v1/farms/{w['farm_a']}/parcels/{w['a1']}/vigor/reprocess").status_code == 403
    assert sql("SELECT count(*) FROM monitoring_jobs WHERE parcel_id = $1", w["a1"])[0][0] == before
