"""T028 - G5: absent gateways and empty referentials degrade to `unavailable` + reason; the last dated advice is kept; nothing is invented."""
import datetime as dt

from tests.helpers import sql
from tests.integration._f4 import (  # noqa: F401
    TODAY4,
    YESTERDAY4,
    call,
    compute,
    seed_plan,
    seed_referentials,
    seed_weather_days,
    world4,
)


def _advice(client, tok, w, parcel):
    return call(client, tok, "GET", f"/v1/farms/{w['farm_a']}/parcels/{parcel}/irrigation/advice")


def test_given_no_weather_url_and_no_forecast_when_computing_then_the_advice_is_unavailable_with_a_reason_and_no_invented_number(client, token_for, world4):
    w = world4
    p = w["p"][9]
    seed_referentials(w["farm_a"], p)
    sql("DELETE FROM irrigation_plans WHERE parcel_id = $1", p)  # derived data, not a protected table: this parcel has never had an advice
    out = compute(w["farm_a"], p)
    assert out["kind"] == "unavailable" and out["unavailable_reason"] in ("gateway_not_configured", "no_weather")
    assert out["total_minutes"] is None and out["net_need_mm"] is None
    r = _advice(client, token_for(w["owner"]), w, p)
    assert r.status_code == 200 and r.json()["kind"] == "unavailable" and r.json()["unavailable_reason"] in ("gateway_not_configured", "no_weather")


def test_given_the_weather_of_today_is_missing_but_an_older_advice_exists_then_it_is_served_dated_with_lowered_confidence_and_never_overwritten(client, token_for, world4):
    w = world4
    p = w["p"][8]
    seed_referentials(w["farm_a"], p)
    sql("UPDATE irrigation_plans SET for_date=$2, kind='irrigate', total_minutes=88, confidence='high' WHERE parcel_id=$1", p, YESTERDAY4)
    out = compute(w["farm_a"], p)  # no forecast row at all: the gateway is not configured
    assert out["kind"] in ("irrigate", "unavailable")
    r = _advice(client, token_for(w["owner"]), w, p)
    body = r.json()
    assert r.status_code == 200 and body["kind"] == "irrigate" and body["total_minutes"] == 88
    assert body["for_date"] == YESTERDAY4.isoformat() and body["is_last_known"] is True and body["confidence"] == "low"
    row = sql("SELECT total_minutes, confidence FROM irrigation_plans WHERE parcel_id=$1 AND for_date=$2", p, YESTERDAY4)[0]
    assert (row["total_minutes"], row["confidence"]) == (88, "high")  # the stored last-known advice is untouched
    assert sql("SELECT count(*) FROM irrigation_plans WHERE parcel_id=$1 AND for_date=$2 AND kind='irrigate'", p, TODAY4)[0][0] == 0


def test_given_a_stale_forecast_then_the_advice_confidence_is_low(client, token_for, world4):
    w = world4
    p = w["p"][7]
    seed_referentials(w["farm_a"], p)
    seed_weather_days(w["farm_a"], age_h=30)
    out = compute(w["farm_a"], p)
    assert out["confidence"] == "low"


def test_given_a_crop_without_a_referential_row_then_the_advice_is_unavailable_no_crop_coefficient_without_default_values(client, token_for, world4):
    w = world4
    p = w["p"][6]
    seed_referentials(w["farm_a"], p, with_crop=False)
    seed_weather_days(w["farm_a"])
    out = compute(w["farm_a"], p)
    assert out["kind"] == "unavailable" and out["unavailable_reason"] == "no_crop_coefficient"
    assert out["total_minutes"] is None and out["net_need_mm"] is None and not any(a["key"] == "kc" for a in out["assumptions"])
    stored = sql("SELECT kind, unavailable_reason FROM irrigation_plans WHERE parcel_id=$1 AND for_date=$2", p, TODAY4)
    assert [tuple(r) for r in stored] == [("unavailable", "no_crop_coefficient")]


def test_given_no_observed_rain_gateway_then_the_past_day_uses_the_last_forecast_and_the_confidence_is_lowered(client, token_for, world4):
    w = world4
    p = w["p"][4]
    seed_referentials(w["farm_a"], p)
    seed_weather_days(w["farm_a"], rain=3.0)
    sql("INSERT INTO water_balance_days (id, farm_id, parcel_id, day, et0_mm, et0_method, kc, etc_mm, rain_mm, rain_source, rain_eff_mm, irrigation_net_mm, taw_mm, raw_mm, depletion_mm)"
        " VALUES (gen_random_uuid(),$1,$2,$3,4,'hargreaves',0.7,2.8,3,'forecast',1.5,0,50,25,5)", w["farm_a"], p, YESTERDAY4 - dt.timedelta(days=1))
    out = compute(w["farm_a"], p)
    days = sql("SELECT rain_source, et0_method FROM water_balance_days WHERE parcel_id=$1 AND day=$2", p, YESTERDAY4)
    assert days and days[0]["rain_source"] == "forecast" and days[0]["et0_method"] == "hargreaves"
    assert out["confidence"] != "high" and any(a["key"] == "rain_source" and a["value"] == "forecast" for a in out["assumptions"])


def test_given_the_f4_routes_then_the_balance_reports_the_gateway_state_without_inventing_days(client, token_for, world4):
    w = world4
    p = w["p"][3]
    r = call(client, token_for(w["owner"]), "GET", f"/v1/farms/{w['farm_a']}/parcels/{p}/irrigation/balance")
    assert r.status_code == 200 and r.json()["days"] == []
    assert r.json()["availability"] in ("ok", "unavailable") and (r.json()["availability"] == "ok" or r.json()["reason"])
