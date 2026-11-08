"""T057 - R3-A1..A4 on the running stack: a created parcel gets an initial history job (duration measured, SC-002); empty imagery gateways publish nothing invented."""
import datetime as dt
import uuid

from tests.e2e._f3 import client, run_job, setup_farm
from tests.helpers import sql
from tests.integration._f3 import seed_scene

TODAY = dt.date.today()


def test_given_a_parcel_just_created_when_the_initial_processing_finishes_then_the_job_duration_is_measured_and_no_value_is_invented_without_imagery():
    with client() as c:
        s = setup_farm(c, 1)
        parcel = s["parcels"][0]
        jobs = sql("SELECT id, kind, state FROM monitoring_jobs WHERE parcel_id = $1", uuid.UUID(parcel))
        assert [(j["kind"], j["state"]) for j in jobs] == [("backfill", "queued")]
        assert c.get(f"/farms/{s['farm']}/parcels/{parcel}/vigor", headers=s["oh"]).json()["processing"] is True
        run_job("backfill_parcel_vigor", farm_id=uuid.UUID(s["farm"]), parcel_id=uuid.UUID(parcel))
        job = sql("SELECT state, duration_s FROM monitoring_jobs WHERE id = $1", jobs[0]["id"])[0]
        assert job["state"] in ("done", "failed") and job["duration_s"] is not None
        b = c.get(f"/farms/{s['farm']}/parcels/{parcel}/vigor", headers=s["oh"]).json()
        assert b["processing"] is False and b["points"] == []


def test_given_a_recent_cloudy_scene_and_an_older_valid_one_when_reading_then_only_the_valid_one_is_served_with_its_date_and_plain_labels():
    with client() as c:
        s = setup_farm(c, 1)
        parcel = uuid.UUID(s["parcels"][0])
        farm = uuid.UUID(s["farm"])
        older = TODAY - dt.timedelta(days=15)
        seed_scene(farm, parcel, acquired_on=older)
        scene = uuid.uuid4()
        sql("INSERT INTO imagery_tiles (tile_id, last_ingested_on) VALUES ('31SBU', $1) ON CONFLICT DO NOTHING", TODAY)
        sql("INSERT INTO imagery_scenes (id, tile_id, acquired_on, cloud_pct_scene, raster_key) VALUES ($1,'31SBU',$2,70,$3)", scene, TODAY - dt.timedelta(days=2), f"rasters/{scene}")
        sql("INSERT INTO parcel_vigor_points (id, farm_id, parcel_id, scene_id, acquired_on, vigor_mean, plant_moisture_mean, clear_pct) VALUES ($1,$2,$3,$4,$5,0.2,0.2,70)",
            uuid.uuid4(), farm, parcel, scene, TODAY - dt.timedelta(days=2))
        r = c.get(f"/farms/{s['farm']}/parcels/{parcel}/vigor", headers=s["oh"])
        b = r.json()
        assert [p["acquired_on"] for p in b["points"]] == [older.isoformat()] and b["last_valid_map"]["acquired_on"] == older.isoformat()
        assert "ndvi" not in r.text.lower() and "ndmi" not in r.text.lower()


def test_given_the_owner_when_requesting_a_reprocessing_then_202_and_a_job_is_queued():
    with client() as c:
        s = setup_farm(c, 1)
        r = c.post(f"/farms/{s['farm']}/parcels/{s['parcels'][0]}/vigor/reprocess", headers=s["oh"])
        assert r.status_code == 202
        assert sql("SELECT count(*) FROM monitoring_jobs WHERE parcel_id = $1 AND kind = 'reprocess'", uuid.UUID(s["parcels"][0]))[0][0] == 1
