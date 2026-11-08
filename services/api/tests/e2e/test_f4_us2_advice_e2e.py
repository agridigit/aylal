"""T056 (US2) - R2-A1..A7 end to end on the Docker stack: simulated weather (seeded forecast), fixture referentials, the plan worker at an
injected instant, then the REST reads. One module-scoped farm (two logins). The API reads with the REAL clock, so a plan computed for
2026-06-04 is served as the dated last known advice (R2-A6) - which is also what the A6 test relies on."""
import datetime as dt
import uuid

import httpx
import pytest

from tests.e2e._f4 import BASE, DAY, NOW, farm_with_worker, run_job, seed_forecast
from tests.helpers import sql

WORKER_FORBIDDEN = ("ece", "ecw", "salin", "water_source", "analysis_age", "soil", "taw", "raw", "moisture", "leaching", "cost")
DRIP = {"kind": "drip", "sectors_count": 2, "emitter_flow_lph": 4, "emitter_spacing_m": 0.5, "row_spacing_m": 2}


def _keys(o):
    if isinstance(o, dict):
        for k, v in o.items():
            yield k
            if k == "key" and isinstance(v, str):
                yield v
            yield from _keys(v)
    elif isinstance(o, list):
        for v in o:
            yield from _keys(v)


def _seed_fixture_referentials(farm, parcel):
    cid, slug = uuid.uuid4(), f"fx_{uuid.uuid4().hex[:10]}"
    sql("INSERT INTO crops (id, slug, name_ary, name_ar, name_fr, cycle) VALUES ($1,$2,$2,$2,$2,'perennial')", cid, slug)
    sql("INSERT INTO seasons (id, farm_id, field_id, crop_id, started_at, stage_corrected) VALUES ($1,$2,$3,$4,$5,'fixture_stage')", uuid.uuid4(), uuid.UUID(farm), uuid.UUID(parcel), cid, dt.date(2026, 3, 1))
    sql("UPDATE parcels SET soil='fixture_soil' WHERE id=$1", uuid.UUID(parcel))
    sql("INSERT INTO crop_irrigation_params (crop_slug, stage_key, kc, root_depth_m, depletion_fraction, ece_threshold_ds_m, ece_max_ds_m, validated, validated_by, source, imported_at)"
        " VALUES ($1,'fixture_stage',0.7,0.5,0.5,2,8,true,'fixture','fixture',now())", slug)
    sql("INSERT INTO soil_textures (texture_key, available_water_mm_per_m, validated_by, source) VALUES ('fixture_soil',100,'fixture','fixture') ON CONFLICT (texture_key) DO NOTHING")
    for key, value in (("effective_rain", '{"method": "fraction", "params": {"fraction": 0.5}}'), ("leaching_max", "0.15"), ("stress_watch_ratio", "0.5")):
        sql("INSERT INTO irrigation_params (key, value, validated_by, source) VALUES ($1,$2::jsonb,'fixture','fixture') ON CONFLICT (key) DO NOTHING", key, value)
    sql("UPDATE farms SET location=ST_SetSRID(ST_MakePoint(-7.6, 33.6), 4326) WHERE id=$1", uuid.UUID(farm))


def _depleted(farm, parcel, depletion=40.0):
    sql("INSERT INTO water_balance_days (id, farm_id, parcel_id, day, et0_mm, et0_method, kc, etc_mm, rain_mm, rain_source, rain_eff_mm, irrigation_net_mm, taw_mm, raw_mm, depletion_mm)"
        " VALUES (gen_random_uuid(),$1,$2,$3,5,'hargreaves',0.7,3.5,0,'forecast',0,0,50,25,$4)", uuid.UUID(farm), uuid.UUID(parcel), DAY - dt.timedelta(days=2), depletion)


@pytest.fixture(scope="module")
def world():
    import os

    mp = pytest.MonkeyPatch()  # the e2e conftest points `sql` at the stack database per test; a module fixture does it itself
    mp.setenv("AYLAL_DATABASE_URL", os.environ["AYLAL_STACK_DATABASE_URL"])
    with httpx.Client(base_url=BASE, verify=False, timeout=60) as c:
        s = farm_with_worker(c, parcels=5, assigned=2)
        p = s["parcels"]
        for parcel in p[:2]:
            assert c.put(f"/farms/{s['farm']}/parcels/{parcel}/irrigation-system", json=DRIP, headers=s["oh"]).status_code == 200
            _seed_fixture_referentials(s["farm"], parcel)
            _depleted(s["farm"], parcel)
        _seed_fixture_referentials(s["farm"], p[3])  # installation missing on purpose
        sql("UPDATE parcels SET irrigation='rainfed' WHERE id=$1", uuid.UUID(p[4]))
        _seed_fixture_referentials(s["farm"], p[4])
        _depleted(s["farm"], p[4])
        yield c, s
    mp.undo()


def _advice(c, s, parcel, who="oh"):
    r = c.get(f"/farms/{s['farm']}/parcels/{parcel}/irrigation/advice", headers=s[who])
    assert r.status_code == 200, r.text
    return r.json()


def _plan(c, s, rain):
    seed_forecast(s["farm"], rain_mm=rain)
    return run_job("compute_irrigation_plans", farm_id=s["farm"], now=NOW)


def test_given_a_rain_above_10_mm_then_the_advice_postpones_and_without_that_rain_it_gives_a_duration_computed_from_the_formula(world):
    c, s = world
    done = _plan(c, s, 11.0)
    assert done["ready_before_7"] is True
    postponed = _advice(c, s, s["parcels"][0])
    assert postponed["kind"] == "postpone_rain" and postponed["total_minutes"] is None and postponed["sectors"] == []
    _plan(c, s, 10.0)  # exactly 10 mm is not "more than 10"
    advice = _advice(c, s, s["parcels"][0])
    assert advice["kind"] == "irrigate" and advice["for_date"] == "2026-06-04"
    value = {a["key"]: a["value"] for a in advice["assumptions"]}
    per_sector = round(advice["net_need_mm"] / (value["efficiency"] * value["application_rate"]) * 60)
    assert [x["minutes"] for x in advice["sectors"]] == [per_sector, per_sector] and advice["total_minutes"] == 2 * per_sector


def test_given_an_advice_then_the_confidence_and_the_five_assumptions_are_available(world):
    c, s = world
    _plan(c, s, 0.0)
    advice = _advice(c, s, s["parcels"][0])
    assert advice["confidence"] in ("high", "medium", "low")
    assert {"et0", "kc", "effective_rain", "soil_texture", "efficiency"} <= {a["key"] for a in advice["assumptions"]}
    assert advice["unavailable_reason"] is None


def test_given_a_computed_day_older_than_the_real_day_then_the_last_known_advice_is_dated_with_a_lowered_confidence(world):
    c, s = world
    _plan(c, s, 0.0)
    advice = _advice(c, s, s["parcels"][0])
    assert advice["is_last_known"] is True and advice["for_date"] == "2026-06-04" and advice["confidence"] == "low"


def test_given_a_rainfed_parcel_then_there_is_no_irrigation_advice_but_a_stress_level(world):
    c, s = world
    _plan(c, s, 0.0)
    advice = _advice(c, s, s["parcels"][4])
    assert advice["kind"] == "rainfed_stress" and advice["total_minutes"] is None and advice["stress_level"] in ("none", "watch", "high")


def test_given_an_irrigated_parcel_without_installation_then_the_advice_is_unavailable_with_the_action_reason(world):
    c, s = world
    _plan(c, s, 0.0)
    advice = _advice(c, s, s["parcels"][3])
    assert advice["kind"] == "unavailable" and advice["unavailable_reason"] == "no_system" and advice["total_minutes"] is None


def test_given_a_worker_then_the_advice_is_the_whitelisted_view_of_the_assigned_parcels_only(world):
    c, s = world
    _plan(c, s, 0.0)
    mine = _advice(c, s, s["mine"][0], "wh")
    assert mine["kind"] == "irrigate" and "leaching_fraction" not in mine
    assert not [k for k in _keys(mine) if k.lower().startswith(WORKER_FORBIDDEN)]
    listing = c.get(f"/farms/{s['farm']}/irrigation/advice", headers=s["wh"]).json()
    assert {i["parcel_id"] for i in listing["items"]} == set(s["mine"])
    hidden = c.get(f"/farms/{s['farm']}/parcels/{s['hidden']}/irrigation/advice", headers=s["wh"])
    unknown = c.get(f"/farms/{s['farm']}/parcels/{uuid.uuid4()}/irrigation/advice", headers=s["wh"])
    assert hidden.status_code == unknown.status_code == 404 and hidden.json() == unknown.json()
