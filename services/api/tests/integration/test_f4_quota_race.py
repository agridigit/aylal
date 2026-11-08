"""T027 - G4: quotas are counted under a per-farm advisory lock in the same transaction as the write; recomputes are coalesced."""
import asyncio
import os
import pathlib
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from tests.helpers import auth, sql
from tests.integration._f4 import TODAY4, seed_analysis, seed_event, sync_event, sync_op, world4  # noqa: F401

APP = pathlib.Path(__file__).resolve().parents[2] / "app"
WORKERS = pathlib.Path(os.environ.get("AYLAL_REPO_DIR", "/repo")) / "services/workers/tasks"
LOCK = "pg_advisory_xact_lock(hashtextextended(CAST(:farm AS text), 0))"


def _race(n, fn):
    with ThreadPoolExecutor(max_workers=n) as pool:
        return list(pool.map(lambda _: fn(), range(n)))


def _post(tok, path, body):
    from app.main import app

    with TestClient(app) as c:
        return c.post(path, headers=auth(tok), json=body)


@pytest.mark.parametrize("rel", ["irrigation/service.py", "sync/irrigation.py"])
def test_given_the_code_then_the_lock_precedes_counting_and_writing(rel):
    text = (APP / rel).read_text(encoding="utf-8")
    assert LOCK in text
    assert text.index(LOCK) < text.index("count(")


def test_given_the_worker_then_a_plan_computation_takes_the_irrigation_farm_lock():
    text = (WORKERS / "compute_irrigation_plans.py").read_text(encoding="utf-8")
    assert "irrigation:" in text and "lock" in text.lower()


def test_given_one_slot_left_in_the_daily_sector_quota_when_two_rest_requests_race_then_exactly_one_passes(client, token_for, world4):
    w = world4
    for _ in range(23):
        seed_event(w["farm_a"], w["a1"], w["owner"], day=TODAY4)
    tok = token_for(w["owner"])
    path = f"/v1/farms/{w['farm_a']}/parcels/{w['a1']}/irrigation/events"

    def one():
        return _post(tok, path, {"id": str(uuid.uuid4()), "performed_on": TODAY4.isoformat(), "duration_min": 10}).status_code

    codes = _race(2, one)
    assert codes.count(201) == 1 and all(c in (201, 409, 422) for c in codes), codes
    assert sql("SELECT count(*) FROM irrigation_events WHERE parcel_id=$1 AND performed_on=$2", w["a1"], TODAY4)[0][0] == 24


def test_given_one_slot_left_in_the_analysis_quota_when_two_rest_requests_race_then_exactly_one_passes(client, token_for, world4):
    w = world4
    for _ in range(49):
        seed_analysis(w["farm_a"], w["a1"], w["owner"])
    tok = token_for(w["owner"])
    path = f"/v1/farms/{w['farm_a']}/parcels/{w['a1']}/water-analyses"
    codes = _race(2, lambda: _post(tok, path, {"id": str(uuid.uuid4()), "ec_ds_m": 2.0, "analysed_on": "2026-06-01"}).status_code)
    assert codes.count(201) == 1 and all(c in (201, 409, 422) for c in codes), codes
    assert sql("SELECT count(*) FROM water_analyses WHERE parcel_id=$1", w["a1"])[0][0] == 50


def test_given_49_versions_when_two_installation_updates_race_then_exactly_one_adds_the_50th(client, token_for, world4):
    w = world4
    sid = sql("SELECT id FROM irrigation_systems WHERE parcel_id=$1", w["a1"])[0][0]
    sql("INSERT INTO irrigation_system_versions (id, farm_id, system_id, parcel_id, snapshot, changed_by, changed_at)"
        " SELECT gen_random_uuid(), $1, $2, $3, '{}'::jsonb, $4, now() FROM generate_series(1, 49)", w["farm_a"], sid, w["a1"], w["owner"])
    tok = token_for(w["owner"])
    from app.main import app

    bodies = iter([{"kind": "drip", "sectors_count": 2, "pump_flow_m3h": 11}, {"kind": "drip", "sectors_count": 3, "pump_flow_m3h": 12}])

    def one():
        with TestClient(app) as c:
            return c.put(f"/v1/farms/{w['farm_a']}/parcels/{w['a1']}/irrigation-system", headers=auth(tok), json=next(bodies)).status_code

    codes = _race(2, one)
    assert sorted(codes) in ([200, 409], [200, 422]), codes
    assert sql("SELECT count(*) FROM irrigation_system_versions WHERE system_id=$1", sid)[0][0] == 50


def test_given_an_active_installation_when_two_sync_uploads_race_to_add_another_one_then_none_is_added(client, token_for, world4):
    w = world4
    p = w["p"][9]
    tok = token_for(w["owner"])
    from app.main import app

    def one():
        op = sync_op("irrigation_systems", w["farm_a"], uuid.uuid4(), {"parcel_id": str(p), "kind": "drip", "sectors_count": 1, "pump_flow_m3h": 5})
        with TestClient(app) as c:
            r = c.post("/v1/sync/upload", headers=auth(tok), json={"ops": [op]})
            return r.status_code, (r.json()["results"][0]["status"] if r.status_code == 200 else None)

    out = _race(2, one)
    assert [s for _, s in out].count("applied") == 0, out  # one active installation per parcel: the parcel already has one
    assert sql("SELECT count(*) FROM irrigation_systems WHERE parcel_id=$1", p)[0][0] == 1


def test_given_a_sync_upload_and_a_rest_call_racing_for_the_last_daily_slot_then_exactly_one_passes(client, token_for, world4):
    w = world4
    for _ in range(23):
        seed_event(w["farm_a"], w["a1"], w["owner"], day=TODAY4)
    tok = token_for(w["owner"])
    from app.main import app

    def rest():
        return _post(tok, f"/v1/farms/{w['farm_a']}/parcels/{w['a1']}/irrigation/events", {"id": str(uuid.uuid4()), "performed_on": TODAY4.isoformat(), "duration_min": 10}).status_code == 201

    def sync():
        with TestClient(app) as c:
            r = c.post("/v1/sync/upload", headers=auth(tok), json={"ops": [sync_event(w["farm_a"], w["a1"], performed_on=TODAY4.isoformat())]})
            return r.status_code == 200 and r.json()["results"][0]["status"] == "applied"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [f.result() for f in (pool.submit(rest), pool.submit(sync))]
    assert results.count(True) == 1, results
    assert sql("SELECT count(*) FROM irrigation_events WHERE parcel_id=$1 AND performed_on=$2", w["a1"], TODAY4)[0][0] == 24


def test_given_back_dated_events_then_the_recompute_jobs_are_coalesced_to_one_active_job_per_parcel_with_the_oldest_date(world4):
    from app.db.session import sessionmaker
    from app.irrigation.service import schedule_recompute

    w = world4

    async def go():
        async with sessionmaker() as s:
            for d in (TODAY4.replace(day=2), TODAY4.replace(day=1), TODAY4.replace(day=3)):
                await schedule_recompute(s, w["farm_a"], w["a1"], d)
            await s.commit()

    asyncio.run(go())
    rows = sql("SELECT from_date, state FROM irrigation_jobs WHERE parcel_id=$1 AND state IN ('queued','running')", w["a1"])
    assert len(rows) == 1 and rows[0]["from_date"] == TODAY4.replace(day=1)


def test_given_5_active_jobs_on_the_farm_when_two_requests_race_for_two_parcels_then_exactly_one_is_scheduled(world4):
    from app.db.session import sessionmaker
    from app.irrigation.service import schedule_recompute

    w = world4
    for i in range(4):
        sql("INSERT INTO irrigation_jobs (id, farm_id, parcel_id, from_date, state) VALUES (gen_random_uuid(),$1,$2,$3,'running')", w["farm_a"], w["p"][5 + i], TODAY4)
    targets = iter([w["p"][3], w["p"][4]])

    def one():
        parcel = next(targets)

        async def go():
            async with sessionmaker() as s:
                try:
                    await schedule_recompute(s, w["farm_a"], parcel, TODAY4)
                    await s.commit()
                    return True
                except Exception:  # noqa: BLE001 - the refusal type is the implementer's choice (409/422 mapped by the router)
                    await s.rollback()
                    return False

        return asyncio.run(go())

    assert _race(2, one).count(True) == 1
    assert sql("SELECT count(*) FROM irrigation_jobs WHERE farm_id=$1 AND state IN ('queued','running')", w["farm_a"])[0][0] == 5
