"""Defect 1 on the running stack - a parcel created through the API is `processing` right after creation, and once the periodic drain has run
its initial-history job is finished (`failed` here: the imagery gateways are empty, no value is invented) and `processing` is false."""
import uuid

from tests.e2e._f3 import client, run_job, setup_farm
from tests.helpers import sql


def test_given_parcels_just_created_when_the_drain_runs_then_every_backfill_job_is_finished_and_processing_falls_back_to_false():
    with client() as c:
        s = setup_farm(c, 3)
        farm = uuid.UUID(s["farm"])
        for p in s["parcels"]:
            assert c.get(f"/farms/{s['farm']}/parcels/{p}/vigor", headers=s["oh"]).json()["processing"] is True
        assert [r["state"] for r in sql("SELECT state FROM monitoring_jobs WHERE farm_id = $1 AND kind = 'backfill'", farm)] == ["queued"] * 3
        assert run_job("drain_backfill_jobs", farm_id=farm) == 3
        jobs = sql("SELECT state, finished_at, duration_s FROM monitoring_jobs WHERE farm_id = $1 AND kind = 'backfill'", farm)
        assert {j["state"] for j in jobs} <= {"done", "failed"} and all(j["finished_at"] and j["duration_s"] is not None for j in jobs)
        for p in s["parcels"]:
            b = c.get(f"/farms/{s['farm']}/parcels/{p}/vigor", headers=s["oh"]).json()
            assert b["processing"] is False and b["points"] == []


def test_given_5_parcels_created_then_drained_when_asking_a_reprocessing_then_it_is_accepted_and_stays_queued():
    with client() as c:
        s = setup_farm(c, 5)
        run_job("drain_backfill_jobs", farm_id=uuid.UUID(s["farm"]))
        r = c.post(f"/farms/{s['farm']}/parcels/{s['parcels'][0]}/vigor/reprocess", headers=s["oh"])
        assert r.status_code == 202
        assert run_job("drain_backfill_jobs", farm_id=uuid.UUID(s["farm"])) == 0  # reprocessing is not the drain's job
