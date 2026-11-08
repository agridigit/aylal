"""T076 (US5) - R5-A1..A4 end to end on the Docker stack: a low then a high salinity (fixture referentials), the worker job at an injected
instant, the durations compared, the worker blind to the analysis. One module-scoped farm (two logins)."""
import uuid

import httpx
import pytest

from tests.e2e._f4 import BASE, NOW, farm_with_worker, run_job, seed_forecast
from tests.e2e.test_f4_us2_advice_e2e import DRIP, _depleted, _keys, _seed_fixture_referentials

WORKER_FORBIDDEN = ("ece", "ecw", "salin", "water_source", "analysis_age", "soil", "taw", "raw", "moisture", "leaching", "cost")


@pytest.fixture(scope="module")
def world():
    import os

    mp = pytest.MonkeyPatch()
    mp.setenv("AYLAL_DATABASE_URL", os.environ["AYLAL_STACK_DATABASE_URL"])
    with httpx.Client(base_url=BASE, verify=False, timeout=60) as c:
        s = farm_with_worker(c, parcels=3, assigned=2)
        for parcel in s["parcels"][:2]:
            assert c.put(f"/farms/{s['farm']}/parcels/{parcel}/irrigation-system", json=DRIP, headers=s["oh"]).status_code == 200
            _seed_fixture_referentials(s["farm"], parcel)
            _depleted(s["farm"], parcel)
        seed_forecast(s["farm"])
        yield c, s
    mp.undo()


def _analysis(c, s, parcel, ec, day):
    return c.post(f"/farms/{s['farm']}/parcels/{parcel}/water-analyses", json={"id": str(uuid.uuid4()), "ec_ds_m": ec, "analysed_on": day, "water_source": "well-42"}, headers=s["oh"])


def _advice(c, s, parcel, who="oh"):
    run_job("compute_irrigation_plans", farm_id=s["farm"], now=NOW)
    return c.get(f"/farms/{s['farm']}/parcels/{parcel}/irrigation/advice", headers=s[who]).json()


def test_given_a_low_then_a_high_salinity_then_the_advice_adds_a_leaching_fraction_and_lengthens_the_duration(world):
    c, s = world
    parcel = s["parcels"][0]
    r = _analysis(c, s, parcel, 1.0, "2026-05-01")
    assert r.status_code == 201 and r.json()["parcel_id"] == parcel
    low = _advice(c, s, parcel)
    assert low["kind"] == "irrigate" and not low["leaching_fraction"]
    assert _analysis(c, s, parcel, 3.1, "2026-05-20").status_code == 201
    high = _advice(c, s, parcel)
    assert high["leaching_fraction"] > 0 and high["total_minutes"] > low["total_minutes"]
    keys = {a["key"]: a["value"] for a in high["assumptions"]}
    assert keys["ece_ds_m"] == 3.1 and "analysis_age_days" in keys and keys["leaching_fraction"] > 0


def test_given_a_salinity_below_the_tolerance_then_no_fraction_is_added(world):
    c, s = world
    parcel = s["parcels"][1]
    assert _analysis(c, s, parcel, 1.5, "2026-05-20").status_code == 201
    advice = _advice(c, s, parcel)
    assert not advice["leaching_fraction"] and not {a["key"]: a["value"] for a in advice["assumptions"]}.get("leaching_fraction")


def test_given_a_worker_then_the_analyses_are_forbidden_and_the_advice_hides_every_trace_of_them(world):
    c, s = world
    parcel = s["mine"][0]
    assert c.get(f"/farms/{s['farm']}/parcels/{parcel}/water-analyses", headers=s["wh"]).status_code == 403
    assert c.post(f"/farms/{s['farm']}/parcels/{parcel}/water-analyses", json={"id": str(uuid.uuid4()), "ec_ds_m": 2.0, "analysed_on": "2026-05-20"}, headers=s["wh"]).status_code == 403
    advice = c.get(f"/farms/{s['farm']}/parcels/{parcel}/irrigation/advice", headers=s["wh"]).json()
    assert "leaching_fraction" not in advice and not [k for k in _keys(advice) if k.lower().startswith(WORKER_FORBIDDEN)]


def test_given_an_invalid_entry_then_422_and_a_future_date_is_refused(world):
    c, s = world
    assert _analysis(c, s, s["parcels"][0], 0, "2026-05-20").status_code == 422
    assert _analysis(c, s, s["parcels"][0], 101, "2026-05-20").status_code == 422
    assert _analysis(c, s, s["parcels"][0], 2.0, "2999-01-01").status_code == 422
