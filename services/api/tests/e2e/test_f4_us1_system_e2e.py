"""T050 (US1) - R1-A1..A5 end to end on the Docker stack: REST + sync, worker forbidden to write. One module-scoped farm (two logins
only: the OTP cap per IP and hour is shared by the whole suite)."""
import uuid

import httpx
import pytest

from tests.e2e._f4 import BASE, farm_with_worker

DRIP = {"kind": "drip", "sectors_count": 2, "emitter_flow_lph": 4, "emitter_spacing_m": 0.5, "row_spacing_m": 2}


@pytest.fixture(scope="module")
def world():
    with httpx.Client(base_url=BASE, verify=False, timeout=60) as c:
        yield c, farm_with_worker(c, parcels=6, assigned=2)


def _url(s, parcel, suffix="irrigation-system"):
    return f"/farms/{s['farm']}/parcels/{parcel}/{suffix}"


def test_given_an_irrigated_parcel_when_the_owner_describes_the_system_then_it_is_attached_with_the_default_efficiency(world):
    c, s = world
    r = c.put(_url(s, s["parcels"][0]), json=DRIP, headers=s["oh"])
    assert r.status_code == 200, r.text
    assert r.json()["parcel_id"] == s["parcels"][0] and r.json()["efficiency_effective"] == 0.9 and r.json()["efficiency_is_default"] is True
    assert round(r.json()["application_rate_mm_h"], 2) == 4.0
    assert c.get(_url(s, s["parcels"][0]), headers=s["oh"]).json()["emitter_flow_lph"] == 4


def test_given_a_pump_described_system_then_it_is_accepted_and_the_pivot_takes_the_sprinkler_default(world):
    c, s = world
    r = c.put(_url(s, s["parcels"][1]), json={"kind": "pivot", "sectors_count": 1, "pump_flow_m3h": 20}, headers=s["oh"])
    assert r.status_code == 200 and r.json()["efficiency_effective"] == 0.75 and r.json()["efficiency_is_default"] is True


def test_given_an_incoherent_value_then_422_names_the_field(world):
    c, s = world
    r = c.put(_url(s, s["parcels"][2]), json={**DRIP, "row_spacing_m": 0}, headers=s["oh"])
    assert r.status_code == 422 and r.json()["field"] == "row_spacing_m" and r.json()["detail"] == "validation"
    assert c.get(_url(s, s["parcels"][2]), headers=s["oh"]).status_code == 404


def test_given_a_system_written_offline_then_the_sync_stores_it_idempotently_and_the_rest_reads_it(world):
    c, s = world
    parcel, rid, op_id = s["parcels"][3], str(uuid.uuid4()), str(uuid.uuid4())
    op = {"op_id": op_id, "table": "irrigation_systems", "kind": "put", "record_id": rid, "farm_id": s["farm"], "base_version": 0,
          "fields": {"parcel_id": parcel, **DRIP}}
    assert c.post("/sync/upload", json={"ops": [op]}, headers=s["oh"]).json()["results"][0]["status"] == "applied"
    assert c.post("/sync/upload", json={"ops": [op]}, headers=s["oh"]).json()["results"][0]["status"] == "duplicate"
    got = c.get(_url(s, parcel), headers=s["oh"]).json()
    assert got["id"] == rid and got["kind"] == "drip"
    versions = c.get(_url(s, parcel, "irrigation-system/versions"), headers=s["oh"]).json()["items"]
    assert len(versions) == 1


def test_given_a_worker_then_writing_is_forbidden_by_rest_and_sync_but_reading_an_assigned_parcel_is_allowed(world):
    c, s = world
    mine, other = s["mine"][0], s["hidden"]
    assert c.get(_url(s, mine), headers=s["wh"]).status_code == 200
    r = c.put(_url(s, mine), json=DRIP, headers=s["wh"])
    assert r.status_code == 403 and r.json() == {"detail": "forbidden"}
    op = {"op_id": str(uuid.uuid4()), "table": "irrigation_systems", "kind": "put", "record_id": str(uuid.uuid4()), "farm_id": s["farm"],
          "base_version": 0, "fields": {"parcel_id": mine, **DRIP}}
    assert c.post("/sync/upload", json={"ops": [op]}, headers=s["wh"]).status_code == 403
    hidden = c.get(_url(s, other), headers=s["wh"])
    unknown = c.get(_url(s, uuid.uuid4()), headers=s["wh"])
    assert hidden.status_code == unknown.status_code == 404 and hidden.json() == unknown.json()
    assert c.get(_url(s, mine, "irrigation-system/versions"), headers=s["wh"]).status_code == 403
