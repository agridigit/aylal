"""T071 (US4) - R4-A1..A3 end to end: volumes recorded through the REST API on two parcels of different surfaces, totals and ratios, the
empty state, the window refusal and the worker's own scope. One module-scoped farm (two logins)."""
import uuid

import httpx
import pytest

from tests.e2e._f4 import BASE, farm_with_worker
from tests.e2e.test_f4_us2_advice_e2e import DRIP


@pytest.fixture(scope="module")
def world():
    import os

    mp = pytest.MonkeyPatch()
    mp.setenv("AYLAL_DATABASE_URL", os.environ["AYLAL_STACK_DATABASE_URL"])
    with httpx.Client(base_url=BASE, verify=False, timeout=60) as c:
        s = farm_with_worker(c, parcels=4, assigned=2)
        for parcel in s["parcels"][:3]:
            assert c.put(f"/farms/{s['farm']}/parcels/{parcel}/irrigation-system", json={**DRIP, "sectors_count": 1}, headers=s["oh"]).status_code == 200
        yield c, s
    mp.undo()


def _record(c, s, parcel, **kw):
    r = c.post(f"/farms/{s['farm']}/parcels/{parcel}/irrigation/events", json={"id": str(uuid.uuid4()), "performed_on": "2026-06-03", **kw}, headers=s["oh"])
    assert r.status_code == 201, r.text
    return r.json()


def _consumption(c, s, who="oh", query=""):
    r = c.get(f"/farms/{s['farm']}/irrigation/consumption{query}", headers=s[who])
    assert r.status_code == 200, r.text
    return r.json()


def test_given_a_farm_without_any_irrigation_then_the_totals_are_zero_for_the_empty_state(world):
    c, s = world
    body = _consumption(c, s, query="?from=2026-01-01&to=2026-12-31")
    assert body["total_m3"] == 0 and all(p["volume_m3"] == 0 for p in body["parcels"])


def test_given_irrigations_on_two_parcels_then_the_volumes_the_totals_and_the_ratios_per_hectare_are_right(world):
    c, s = world
    a, b = _record(c, s, s["parcels"][0], duration_min=60), _record(c, s, s["parcels"][1], duration_min=120)
    rows = {p["parcel_id"]: p for p in _consumption(c, s, query="?from=2026-01-01&to=2026-12-31")["parcels"]}
    ra, rb = rows[s["parcels"][0]], rows[s["parcels"][1]]
    assert abs(ra["volume_m3"] - a["volume_m3"]) < 1e-6 and abs(rb["volume_m3"] - b["volume_m3"]) < 1e-6
    assert abs(ra["volume_m3_per_ha"] - ra["volume_m3"] / ra["area_ha"]) < 1e-6
    assert abs(_consumption(c, s, query="?from=2026-01-01&to=2026-12-31")["total_m3"] - (a["volume_m3"] + b["volume_m3"])) < 1e-6


def test_given_a_worker_then_the_totals_cover_only_their_assigned_parcels(world):
    c, s = world
    _record(c, s, s["parcels"][2], duration_min=30)  # a parcel the worker is NOT assigned to
    mine = _consumption(c, s, "wh", "?from=2026-01-01&to=2026-12-31")
    assert {p["parcel_id"] for p in mine["parcels"]} == set(s["mine"]) and s["parcels"][2] not in str(mine)
    owner = _consumption(c, s, query="?from=2026-01-01&to=2026-12-31")
    assert mine["total_m3"] < owner["total_m3"]


def test_given_a_window_over_24_months_then_422_before_any_read(world):
    c, s = world
    assert c.get(f"/farms/{s['farm']}/irrigation/consumption?from=2023-01-01&to=2026-06-04", headers=s["oh"]).status_code == 422
