"""T041 - R1-A1, R1-A2, edge cases: the weather is read from the stored farm forecast (today + 7 days), never fetched by a request."""
import datetime as dt
import json

import pytest

from tests.helpers import sql
from tests.integration._f3 import call, flush_redis, world3  # noqa: F401

TODAY = dt.date.today()


def _days(first, last):
    return [{"date": (TODAY + dt.timedelta(days=i)).isoformat(), "tmin": 3, "tmax": 15, "rain_mm": 1, "wind_kmh": 9, "humidity_pct": 55, "icon": "cloud"} for i in range(first, last + 1)]


def _store(farm, days, *, age_h=1, availability="ok", reason=None):
    sql("INSERT INTO farm_weather (farm_id, cell_id, fetched_at, availability, reason, days) VALUES ($1,'33.6:-7.6',now() - $2 * interval '1 hour',$3,$4,$5::jsonb)"
        " ON CONFLICT (farm_id) DO UPDATE SET fetched_at = EXCLUDED.fetched_at, availability = EXCLUDED.availability, reason = EXCLUDED.reason, days = EXCLUDED.days",
        farm, age_h, availability, reason, json.dumps(days))


def _locate(farm):
    sql("UPDATE farms SET location = ST_SetSRID(ST_MakePoint(-7.6, 33.57), 4326) WHERE id = $1", farm)


@pytest.fixture(autouse=True)
def _clean():
    flush_redis()


def test_given_a_located_farm_when_opening_the_weather_then_today_and_the_7_next_days_are_served_with_the_four_values_and_an_icon(client, token_for, world3):
    w = world3
    _locate(w["farm_a"])
    _store(w["farm_a"], _days(0, 7))
    b = call(client, token_for(w["owner"]), "GET", f"/v1/farms/{w['farm_a']}/weather").json()
    assert b["availability"] == "ok" and [d["date"] for d in b["days"]] == [d["date"] for d in _days(0, 7)]
    assert all({"tmin", "tmax", "rain_mm", "wind_kmh", "humidity_pct", "icon"} <= set(d) for d in b["days"])


def test_given_a_stored_forecast_with_past_and_far_days_when_opening_the_weather_then_only_today_to_day_7_is_served(client, token_for, world3):
    w = world3
    _locate(w["farm_a"])
    _store(w["farm_a"], _days(-2, 9))
    days = call(client, token_for(w["owner"]), "GET", f"/v1/farms/{w['farm_a']}/weather").json()["days"]
    assert [d["date"] for d in days] == [d["date"] for d in _days(0, 7)]


def test_given_the_same_forecast_when_a_worker_opens_the_dashboard_then_the_weather_is_the_same_farm_level_data(client, token_for, world3):
    w = world3
    _locate(w["farm_a"])
    _store(w["farm_a"], _days(-1, 8))
    b = call(client, token_for(w["worker"]), "GET", f"/v1/farms/{w['farm_a']}/dashboard").json()
    assert [d["date"] for d in b["weather"]["days"]] == [d["date"] for d in _days(0, 7)]


def test_given_no_network_data_older_than_24_hours_when_opening_the_dashboard_then_it_is_stale_kept_and_dated(client, token_for, world3):
    w = world3
    _locate(w["farm_a"])
    _store(w["farm_a"], _days(0, 7), age_h=30)
    b = call(client, token_for(w["owner"]), "GET", f"/v1/farms/{w['farm_a']}/dashboard").json()["weather"]
    assert b["availability"] == "stale" and b["fetched_at"] and len(b["days"]) == 8


def test_given_a_farm_without_location_and_no_forecast_when_opening_the_weather_then_the_reason_is_farm_not_located(client, token_for, world3):
    w = world3
    r = call(client, token_for(w["owner"]), "GET", f"/v1/farms/{w['farm_a']}/weather")
    assert r.status_code == 200
    assert r.json()["availability"] == "unavailable" and r.json()["reason"] == "farm_not_located" and not r.json().get("days")


def test_given_a_located_farm_and_no_gateway_when_opening_the_weather_then_the_reason_is_gateway_not_configured_with_no_value(client, token_for, world3, monkeypatch):
    w = world3  # fresh farm: no farm_weather row exists yet
    monkeypatch.delenv("AYLAL_WEATHER_URL", raising=False)
    _locate(w["farm_a"])
    b = call(client, token_for(w["owner"]), "GET", f"/v1/farms/{w['farm_a']}/weather").json()
    assert b["reason"] == "gateway_not_configured" and not b.get("days")


def test_given_a_farm_without_parcel_when_opening_the_dashboard_then_the_weather_shows_and_the_parcel_list_is_empty(client, token_for, make_farm):
    from tests.integration._f2 import new_user

    owner = new_user()
    farm = make_farm({owner: "owner"})
    _locate(farm)
    _store(farm, _days(0, 7))
    b = call(client, token_for(owner), "GET", f"/v1/farms/{farm}/dashboard").json()
    assert b["parcels"] == [] and b["counts"] == {"red": 0, "orange": 0, "green": 0} and len(b["weather"]["days"]) == 8


def test_given_a_request_when_reading_the_weather_then_no_outbound_call_is_made(client, token_for, world3, monkeypatch):
    import app.monitoring.gateways as g

    calls = []
    monkeypatch.setattr(g, "_default_http", lambda *a, **k: calls.append(a))
    w = world3
    call(client, token_for(w["owner"]), "GET", f"/v1/farms/{w['farm_a']}/weather")
    call(client, token_for(w["owner"]), "GET", f"/v1/farms/{w['farm_a']}/dashboard")
    assert calls == []
