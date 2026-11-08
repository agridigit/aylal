"""T053 (US2) - R2-A1..A7 on the real stack of components (PostgreSQL, Redis): the daily advice, read from the cache only,
with the injected clock (02:00 local on 2026-06-04). Worker: the whitelisted view of assigned, non archived parcels only."""
import uuid

import pytest

from tests.helpers import sql
from tests.integration._f4 import (  # noqa: F401
    FORBIDDEN,
    NOT_FOUND,
    TODAY4,
    YESTERDAY4,
    assert_worker_safe,
    call,
    compute,
    seed_plan,
    world4,
)
from tests.integration._f4_us import (
    advice_url,
    assumption,
    depleted_parcel,
    plan_of,
    seed_referentials,
)

STAFF_KEYS = {"et0", "kc", "effective_rain", "efficiency", "soil_texture"}


def _advice(client, token_for, w, parcel, who="owner"):
    r = call(client, token_for(w[who]), "GET", advice_url(w, parcel))
    assert r.status_code == 200, r.text
    return r.json()


def test_given_an_irrigated_parcel_with_a_system_when_the_weather_of_the_day_is_available_then_the_advice_is_ready_before_7(client, token_for, world4):
    w = world4
    parcel = depleted_parcel(w)
    assert compute(w["farm_a"], parcel)["kind"] == "irrigate"
    advice = _advice(client, token_for, w, parcel)
    assert advice["kind"] == "irrigate" and advice["for_date"] == "2026-06-04" and advice["ready_before_7"] is True
    assert advice["total_minutes"] and advice["total_minutes"] > 0 and len(advice["sectors"]) == 2


@pytest.mark.parametrize("rain,kind", [(11.0, "postpone_rain"), (10.1, "postpone_rain"), (10.0, "irrigate"), (9.9, "irrigate")])
def test_given_a_rain_forecast_when_the_advice_is_computed_then_it_postpones_only_above_10_mm_strictly(client, token_for, world4, rain, kind):
    w = world4
    parcel = depleted_parcel(w, f"R{rain}", rain=rain)
    compute(w["farm_a"], parcel)
    advice = _advice(client, token_for, w, parcel)
    assert advice["kind"] == kind
    if kind == "postpone_rain":
        assert advice["total_minutes"] is None and advice["sectors"] == []


def test_given_an_advice_when_opened_then_it_carries_the_confidence_and_the_five_assumptions(client, token_for, world4):
    w = world4
    parcel = depleted_parcel(w)
    compute(w["farm_a"], parcel)
    advice = _advice(client, token_for, w, parcel)
    assert advice["confidence"] in ("high", "medium", "low")
    assert STAFF_KEYS <= {a["key"] for a in advice["assumptions"]}
    assert all(a["source"] in ("referential", "gateway", "computed", "default", "user", "sensor") for a in advice["assumptions"])
    day = call(client, token_for(w["owner"]), "GET", f"/v1/farms/{w['farm_a']}/parcels/{parcel}/irrigation/balance").json()
    assert day["availability"] == "ok" and day["days"][-1]["day"] == "2026-06-04" and {"et0_mm", "kc", "etc_mm", "depletion_mm"} <= set(day["days"][-1])


def test_given_a_net_need_when_the_duration_is_determined_then_it_is_the_need_over_efficiency_times_the_rate(client, token_for, world4):
    w = world4
    parcel = depleted_parcel(w, sectors=2)
    compute(w["farm_a"], parcel)
    advice = _advice(client, token_for, w, parcel)
    efficiency, rate = assumption(advice, "efficiency")["value"], assumption(advice, "application_rate")["value"]
    assert (efficiency, rate) == (0.9, 4.0)
    per_sector = round(advice["net_need_mm"] / (efficiency * rate) * 60)
    assert [s["minutes"] for s in advice["sectors"]] == [per_sector, per_sector]
    assert advice["total_minutes"] == 2 * per_sector


def test_given_an_unknown_soil_when_the_balance_is_computed_then_the_weakest_reserve_applies_and_the_assumptions_flag_it(client, token_for, world4):
    w = world4
    parcel = depleted_parcel(w, "Soil")
    sql("UPDATE parcels SET soil=NULL WHERE id=$1", parcel)
    compute(w["farm_a"], parcel)
    advice = _advice(client, token_for, w, parcel)
    soil = assumption(advice, "soil_texture")
    assert soil is not None and soil["source"] == "default", soil
    weakest = float(sql("SELECT min(available_water_mm_per_m) FROM soil_textures WHERE available_water_mm_per_m IS NOT NULL")[0][0])
    assert abs(assumption(advice, "taw_mm")["value"] - weakest * 0.5) < 0.1  # fixture root depth 0.5 m


def test_given_a_known_soil_then_the_assumption_is_not_flagged_as_a_default(client, token_for, world4):
    w = world4
    parcel = depleted_parcel(w, "Known")
    compute(w["farm_a"], parcel)
    assert assumption(_advice(client, token_for, w, parcel), "soil_texture")["source"] == "referential"


def test_given_no_weather_of_the_day_when_opening_then_the_last_known_advice_is_shown_dated_with_a_lower_confidence(client, token_for, world4):
    w = world4
    parcel = depleted_parcel(w, "Stale")
    sql("DELETE FROM farm_weather WHERE farm_id=$1", w["farm_a"])
    seed_plan(w["farm_a"], parcel, kind="irrigate", day=YESTERDAY4, minutes=90)
    compute(w["farm_a"], parcel)  # nothing may be written for the day without weather while a valid advice exists
    assert plan_of(parcel) is None
    advice = _advice(client, token_for, w, parcel)
    assert advice["is_last_known"] is True and advice["for_date"] == "2026-06-03" and advice["confidence"] == "low" and advice["kind"] == "irrigate"


def test_given_a_rainfed_parcel_then_no_irrigation_advice_is_produced_and_a_stress_indicator_is_shown(client, token_for, world4):
    w = world4
    parcel = depleted_parcel(w, "Rainfed", with_system=False)
    sql("UPDATE parcels SET irrigation='rainfed' WHERE id=$1", parcel)
    compute(w["farm_a"], parcel)
    advice = _advice(client, token_for, w, parcel)
    assert advice["kind"] == "rainfed_stress" and advice["total_minutes"] is None and advice["sectors"] == []
    assert advice["stress_level"] in ("none", "watch", "high")
    listing = call(client, token_for(w["owner"]), "GET", f"/v1/farms/{w['farm_a']}/irrigation/advice?limit=100").json()
    assert next(i for i in listing["items"] if i["parcel_id"] == str(parcel))["kind"] == "rainfed_stress"


def test_given_an_irrigated_parcel_without_system_then_the_advice_is_unavailable_with_no_number(client, token_for, world4):
    w = world4
    parcel = depleted_parcel(w, "NoSys", with_system=False)
    compute(w["farm_a"], parcel)
    advice = _advice(client, token_for, w, parcel)
    assert advice["kind"] == "unavailable" and advice["unavailable_reason"] == "no_system" and advice["total_minutes"] is None and advice["net_need_mm"] is None


def test_given_a_greenhouse_parcel_then_the_rain_is_ignored_and_never_postpones(client, token_for, world4):
    w = world4
    parcel = depleted_parcel(w, "Green", rain=15.0)
    sql("UPDATE parcels SET greenhouse=true WHERE id=$1", parcel)
    compute(w["farm_a"], parcel)
    advice = _advice(client, token_for, w, parcel)
    assert advice["kind"] == "irrigate" and assumption(advice, "effective_rain")["value"] == 0


def test_given_reads_then_the_advice_endpoints_only_read_the_stored_plans_and_compute_nothing(client, token_for, world4):
    w = world4
    parcel = depleted_parcel(w, "ReadOnly")
    plans, days = sql("SELECT count(*) FROM irrigation_plans")[0][0], sql("SELECT count(*) FROM water_balance_days")[0][0]
    for _ in range(2):
        call(client, token_for(w["owner"]), "GET", advice_url(w, parcel))
        call(client, token_for(w["owner"]), "GET", f"/v1/farms/{w['farm_a']}/irrigation/advice")
        call(client, token_for(w["owner"]), "GET", f"/v1/farms/{w['farm_a']}/parcels/{parcel}/irrigation/balance")
    assert (sql("SELECT count(*) FROM irrigation_plans")[0][0], sql("SELECT count(*) FROM water_balance_days")[0][0]) == (plans, days)
    assert call(client, token_for(w["owner"]), "GET", advice_url(w, parcel)).json()["kind"] == "unavailable"  # not computed yet: nothing invented


def test_given_a_worker_then_the_advice_is_the_whitelisted_view_of_assigned_parcels_without_soil_water_or_leaching_data(client, token_for, world4):
    w = world4
    seed_referentials(w["farm_a"], w["a1"])
    tok = token_for(w["worker"])
    one = call(client, tok, "GET", advice_url(w, w["a1"])).json()
    assert "leaching_fraction" not in one and {a["key"] for a in one["assumptions"]} <= {"et0", "kc", "effective_rain", "efficiency", "application_rate", "rain_source"}
    assert_worker_safe(one, "getAdvice")
    listing = call(client, tok, "GET", f"/v1/farms/{w['farm_a']}/irrigation/advice?limit=100").json()
    assert {i["parcel_id"] for i in listing["items"]} == {str(p) for p in w["p"][:3]}
    assert_worker_safe(listing, "listAdvice")
    staff = call(client, token_for(w["owner"]), "GET", advice_url(w, w["a1"])).json()
    assert "leaching_fraction" in staff and any(a["key"] == "soil_texture" for a in staff["assumptions"])
    balance = call(client, tok, "GET", f"/v1/farms/{w['farm_a']}/parcels/{w['a1']}/irrigation/balance").json()
    assert_worker_safe(balance, "getBalance")


def test_given_a_hidden_unknown_archived_or_foreign_parcel_then_the_answer_is_one_identical_404(client, token_for, world4):
    w = world4
    tok = token_for(w["worker"])
    sql("UPDATE parcels SET archived_at=now() WHERE id=$1", w["p"][2])
    answers = [call(client, tok, "GET", advice_url(w, p)) for p in (w["hidden"], uuid.uuid4(), w["p"][2])]
    answers.append(call(client, token_for(w["owner_b"]), "GET", advice_url(w, w["a1"])))
    assert {(a.status_code, str(a.json())) for a in answers} == {(404, str(NOT_FOUND))}
    listing = call(client, tok, "GET", f"/v1/farms/{w['farm_a']}/irrigation/advice?limit=100").json()
    assert {i["parcel_id"] for i in listing["items"]} == {str(p) for p in w["p"][:2]} and listing["to_irrigate_count"] <= 2
