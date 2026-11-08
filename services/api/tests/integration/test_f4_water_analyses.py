"""T075 (US5) - R5-A1..A4: water analyses (real PostgreSQL): attached to the parcel, caps, staff only, never deleted, the advice is
recomputed and adds a leaching fraction above the crop threshold (fixture referentials: threshold 2, max 8, leaching_max 0.15)."""
import uuid

import pytest

from tests.helpers import sql
from tests.integration._f4 import (  # noqa: F401
    FORBIDDEN,
    NOT_FOUND,
    assert_worker_safe,
    call,
    compute,
    seed_analysis,
    world4,
)
from tests.integration._f4_us import advice_url, assumption, depleted_parcel, seed_analysis_on


def _url(w, parcel, suffix="water-analyses"):
    return f"/v1/farms/{w['farm_a']}/parcels/{parcel}/{suffix}"


def _body(**over):
    return {"id": str(uuid.uuid4()), "ec_ds_m": 2.4, "analysed_on": "2026-05-20", "water_source": "well-42", **over}


def _advice(client, token_for, w, parcel, who="owner"):
    return call(client, token_for(w[who]), "GET", advice_url(w, parcel)).json()


def test_given_an_irrigated_parcel_when_the_owner_enters_the_salinity_with_its_date_then_it_is_attached_to_the_parcel_and_listed(client, token_for, world4):
    w = world4
    body = _body()
    r = call(client, token_for(w["owner"]), "POST", _url(w, w["a1"]), body)
    assert r.status_code == 201, r.text
    assert r.json()["parcel_id"] == str(w["a1"]) and r.json()["ec_ds_m"] == 2.4 and r.json()["water_source"] == "well-42" and r.json()["age_days"] == 15
    listed = call(client, token_for(w["manager"]), "GET", _url(w, w["a1"])).json()["items"]
    assert [i["id"] for i in listed] == [body["id"]]
    assert sql("SELECT author_id FROM water_analyses WHERE id=$1", uuid.UUID(body["id"]))[0][0] == w["owner"]


@pytest.mark.parametrize("patch,status", [({"ec_ds_m": 100}, 201), ({"ec_ds_m": 100.1}, 422), ({"ec_ds_m": 0}, 422), ({"ec_ds_m": -1}, 422),
                                          ({"analysed_on": "2026-06-04"}, 201), ({"analysed_on": "2026-06-05"}, 422)])
def test_given_a_salinity_or_a_date_at_the_limit_or_beyond_then_the_caps_apply_with_the_injected_clock(client, token_for, world4, patch, status):
    w = world4
    r = call(client, token_for(w["owner"]), "POST", _url(w, w["a1"]), _body(**patch))
    assert r.status_code == status, r.text
    if status == 422:
        assert sql("SELECT count(*) FROM water_analyses WHERE parcel_id=$1", w["a1"])[0][0] == 0


def test_given_50_analyses_on_the_parcel_then_the_51st_is_refused(client, token_for, world4):
    w = world4
    for _ in range(50):
        seed_analysis(w["farm_a"], w["a1"], w["owner"])
    r = call(client, token_for(w["owner"]), "POST", _url(w, w["a1"]), _body())
    assert r.status_code == 409 and r.json()["detail"] == "quota_exceeded"


def test_given_the_same_id_replayed_then_it_is_a_200_without_a_new_row_and_another_farms_id_is_a_404(client, token_for, world4):
    w = world4
    body = _body()
    assert call(client, token_for(w["owner"]), "POST", _url(w, w["a1"]), body).status_code == 201
    assert call(client, token_for(w["owner"]), "POST", _url(w, w["a1"]), body).status_code == 200
    assert sql("SELECT count(*) FROM water_analyses WHERE id=$1", uuid.UUID(body["id"]))[0][0] == 1
    foreign = _body()
    assert call(client, token_for(w["owner_b"]), "POST", _url({**w, "farm_a": w["farm_b"]}, w["b1"]), foreign).status_code == 201
    other = call(client, token_for(w["owner"]), "POST", _url(w, w["a1"]), foreign)
    assert other.status_code == 404 and other.json() == NOT_FOUND


def test_given_an_analysis_then_there_is_no_way_to_delete_it(client, token_for, world4):
    w = world4
    body = _body()
    call(client, token_for(w["owner"]), "POST", _url(w, w["a1"]), body)
    for path in (_url(w, w["a1"], f"water-analyses/{body['id']}"), _url(w, w["a1"])):
        assert call(client, token_for(w["owner"]), "DELETE", path).status_code in (404, 405)
    assert sql("SELECT count(*) FROM water_analyses WHERE id=$1", uuid.UUID(body["id"]))[0][0] == 1


def test_given_a_worker_then_reading_and_writing_analyses_are_403_with_nothing_stored(client, token_for, world4):
    w = world4
    tok = token_for(w["worker"])
    seed_analysis(w["farm_a"], w["a1"], w["owner"])
    assert call(client, tok, "GET", _url(w, w["a1"])).json() == FORBIDDEN
    r = call(client, tok, "POST", _url(w, w["a1"]), _body())
    assert r.status_code == 403 and r.json() == FORBIDDEN
    assert sql("SELECT count(*) FROM water_analyses WHERE parcel_id=$1", w["a1"])[0][0] == 1


def test_given_an_archived_unknown_or_foreign_parcel_then_staff_get_the_same_404(client, token_for, world4):
    w = world4
    sql("UPDATE parcels SET archived_at=now() WHERE id=$1", w["p"][4])
    answers = [call(client, token_for(w["owner"]), "POST", _url(w, p), _body()) for p in (w["p"][4], uuid.uuid4())]
    answers.append(call(client, token_for(w["owner_b"]), "POST", _url(w, w["a1"]), _body()))
    assert {(a.status_code, str(a.json())) for a in answers} == {(404, str(NOT_FOUND))}


def test_given_a_new_analysis_then_a_recompute_of_the_advice_is_scheduled_for_the_parcel(client, token_for, world4):
    w = world4
    parcel = depleted_parcel(w, "Sched")
    assert call(client, token_for(w["owner"]), "POST", _url(w, parcel), _body()).status_code == 201
    assert sql("SELECT count(*) FROM irrigation_jobs WHERE parcel_id=$1 AND state='queued'", parcel)[0][0] == 1


def test_given_a_low_then_a_high_salinity_when_the_advice_is_computed_then_the_leaching_fraction_lengthens_the_duration_and_is_stated(client, token_for, world4):
    w = world4
    parcel = depleted_parcel(w, "Salt")
    tok = token_for(w["owner"])
    call(client, tok, "POST", _url(w, parcel), _body(ec_ds_m=1.0, analysed_on="2026-05-01"))
    compute(w["farm_a"], parcel)
    low = _advice(client, token_for, w, parcel)
    assert low["kind"] == "irrigate" and not low["leaching_fraction"] and not (assumption(low, "leaching_fraction") or {}).get("value")
    call(client, tok, "POST", _url(w, parcel), _body(ec_ds_m=3.1, analysed_on="2026-05-20"))
    compute(w["farm_a"], parcel)
    high = _advice(client, token_for, w, parcel)
    lr = 3.1 / (40 - 3.1)
    assert abs(high["leaching_fraction"] - lr) < 1e-3 and abs(assumption(high, "leaching_fraction")["value"] - lr) < 1e-3
    assert high["total_minutes"] > low["total_minutes"] and abs(high["net_need_mm"] - low["net_need_mm"] / (1 - lr)) < 0.2


def test_given_an_old_analysis_then_its_age_is_stated_in_the_assumptions(client, token_for, world4):
    w = world4
    parcel = depleted_parcel(w, "Old")
    seed_analysis_on(w["farm_a"], parcel, w["owner"], 3.1, day=__import__("datetime").date(2025, 6, 4))
    compute(w["farm_a"], parcel)
    assert assumption(_advice(client, token_for, w, parcel), "analysis_age_days")["value"] == 365


def test_given_the_crop_has_no_salinity_reference_then_no_leaching_is_added_and_the_reason_is_stated(client, token_for, world4):
    w = world4
    parcel = depleted_parcel(w, "NoRef")
    seed_analysis_on(w["farm_a"], parcel, w["owner"], 3.1)
    sql("UPDATE crop_irrigation_params SET ece_max_ds_m=NULL WHERE crop_slug IN (SELECT c.slug FROM seasons s JOIN crops c ON c.id=s.crop_id WHERE s.field_id=$1)", parcel)
    compute(w["farm_a"], parcel)
    advice = _advice(client, token_for, w, parcel)
    assert not advice["leaching_fraction"] and assumption(advice, "leaching_fraction") is None
    assert assumption(advice, "leaching_unavailable_reason")["value"] == "no_salinity_reference"


def test_given_a_computed_advice_with_an_analysis_then_the_worker_never_sees_salinity_source_age_or_leaching_but_staff_do(client, token_for, world4):
    w = world4
    seed_analysis_on(w["farm_a"], w["a1"], w["owner"], 3.1)
    from tests.integration._f4_us import seed_referentials, seed_weather_days

    seed_referentials(w["farm_a"], w["a1"])
    seed_weather_days(w["farm_a"])
    sql("INSERT INTO water_balance_days (id, farm_id, parcel_id, day, et0_mm, et0_method, kc, etc_mm, rain_mm, rain_source, rain_eff_mm, irrigation_net_mm, taw_mm, raw_mm, depletion_mm)"
        " VALUES (gen_random_uuid(),$1,$2,'2026-06-02',5,'hargreaves',0.7,3.5,0,'forecast',0,0,50,25,40)", w["farm_a"], w["a1"])
    sql("DELETE FROM irrigation_plans WHERE parcel_id=$1", w["a1"])
    compute(w["farm_a"], w["a1"])
    staff = _advice(client, token_for, w, w["a1"])
    assert {"ece_ds_m", "water_source", "analysis_age_days"} <= {a["key"] for a in staff["assumptions"]}
    worker = _advice(client, token_for, w, w["a1"], "worker")
    assert_worker_safe(worker, "getAdvice with an analysis")
    assert "leaching_fraction" not in worker and worker["kind"] == staff["kind"]
