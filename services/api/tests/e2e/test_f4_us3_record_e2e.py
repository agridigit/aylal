"""T061 (US3) - R3-A1..A5 end to end on the Docker stack: record from the advice (REST), offline replay (sync, idempotent), the F6
journal without double entry, the next-day balance. One module-scoped farm (two logins); time = injected instants for the worker job."""
import uuid

import httpx
import pytest

from tests.e2e._f4 import BASE, NOW, farm_with_worker, run_job, seed_forecast
from tests.e2e.test_f4_us2_advice_e2e import DRIP, _depleted, _seed_fixture_referentials
from tests.helpers import sql

NEXT_DAY = "2026-06-05T01:00:00+00:00"


@pytest.fixture(scope="module")
def world():
    import os

    mp = pytest.MonkeyPatch()
    mp.setenv("AYLAL_DATABASE_URL", os.environ["AYLAL_STACK_DATABASE_URL"])
    with httpx.Client(base_url=BASE, verify=False, timeout=60) as c:
        s = farm_with_worker(c, parcels=4, assigned=2)
        for parcel in s["parcels"][:2]:
            assert c.put(f"/farms/{s['farm']}/parcels/{parcel}/irrigation-system", json=DRIP, headers=s["oh"]).status_code == 200
            _seed_fixture_referentials(s["farm"], parcel)
            _depleted(s["farm"], parcel)
        seed_forecast(s["farm"])
        run_job("compute_irrigation_plans", farm_id=s["farm"], now=NOW)
        yield c, s
    mp.undo()


def _events(s, parcel):
    return f"/farms/{s['farm']}/parcels/{parcel}/irrigation/events"


def test_given_the_advice_when_the_owner_confirms_done_then_the_irrigation_is_recorded_and_appears_once_in_the_journal(world):
    c, s = world
    parcel = s["parcels"][0]
    advice = c.get(f"/farms/{s['farm']}/parcels/{parcel}/irrigation/advice", headers=s["oh"]).json()
    assert advice["kind"] == "irrigate"
    body = {"id": str(uuid.uuid4()), "performed_on": "2026-06-04", "duration_min": advice["sectors"][0]["minutes"], "sector_no": 1}
    r = c.post(_events(s, parcel), json=body, headers=s["oh"])
    assert r.status_code == 201 and r.json()["volume_m3"] > 0
    assert c.post(_events(s, parcel), json=body, headers=s["oh"]).status_code == 200  # replay
    journal = c.get(f"/farms/{s['farm']}/operations?type=irrigation&parcel_id={parcel}&limit=100", headers=s["oh"]).json()["items"]
    assert [i["id"] for i in journal].count(r.json()["operation_id"]) == 1


def test_given_a_duration_then_a_volume_the_conversions_agree(world):
    c, s = world
    parcel = s["parcels"][1]
    first = c.post(_events(s, parcel), json={"id": str(uuid.uuid4()), "performed_on": "2026-06-03", "duration_min": 60}, headers=s["oh"]).json()
    second = c.post(_events(s, parcel), json={"id": str(uuid.uuid4()), "performed_on": "2026-06-03", "volume_m3": first["volume_m3"]}, headers=s["oh"]).json()
    assert second["duration_min"] == 60


def test_given_an_offline_record_when_replayed_twice_through_the_sync_then_one_event_and_one_operation_exist(world):
    c, s = world
    parcel, rid = s["mine"][1], str(uuid.uuid4())
    op = {"op_id": str(uuid.uuid4()), "table": "irrigation_events", "kind": "put", "record_id": rid, "farm_id": s["farm"], "base_version": 0,
          "fields": {"parcel_id": parcel, "performed_on": "2026-06-03", "duration_min": 45}}
    assert c.post("/sync/upload", json={"ops": [op]}, headers=s["wh"]).json()["results"][0]["status"] == "applied"
    assert c.post("/sync/upload", json={"ops": [op]}, headers=s["wh"]).json()["results"][0]["status"] == "duplicate"
    assert sql("SELECT count(*) FROM irrigation_events WHERE id=$1", uuid.UUID(rid))[0][0] == 1
    assert sql("SELECT count(*) FROM operations WHERE type='irrigation' AND author_id=$1 AND performed_on=$2", uuid.UUID(s["worker_id"]), __import__("datetime").date(2026, 6, 3))[0][0] >= 1


def test_given_a_recorded_irrigation_when_the_plans_are_recomputed_the_next_day_then_the_balance_counts_it(world):
    c, s = world
    parcel = s["parcels"][0]
    run_job("compute_irrigation_plans", farm_id=s["farm"], now=NEXT_DAY)
    days = c.get(f"/farms/{s['farm']}/parcels/{parcel}/irrigation/balance?from=2026-06-01&to=2026-06-06", headers=s["oh"]).json()["days"]
    applied = next(d for d in days if d["day"] == "2026-06-04")
    assert applied["irrigation_net_mm"] > 0


def test_given_a_worker_then_they_cannot_record_or_cancel_on_a_hidden_parcel_nor_cancel_the_owners_event(world):
    c, s = world
    hidden = c.post(_events(s, s["hidden"]), json={"id": str(uuid.uuid4()), "performed_on": "2026-06-03", "duration_min": 30}, headers=s["wh"])
    unknown = c.post(_events(s, str(uuid.uuid4())), json={"id": str(uuid.uuid4()), "performed_on": "2026-06-03", "duration_min": 30}, headers=s["wh"])
    assert hidden.status_code == unknown.status_code == 404 and hidden.json() == unknown.json()
    owner_event = c.get(_events(s, s["parcels"][0]), headers=s["oh"]).json()["items"][0]["id"]
    assert c.post(f"{_events(s, s['mine'][0])}/{owner_event}/cancel", headers=s["wh"]).status_code in (403, 404)
