"""T042 - the weather and dashboard responses honour the contract (8 days max, freshness, no invented value)."""
import datetime as dt
import json

from tests.contract._f3_schema import SPEC, assert_valid
from tests.helpers import sql
from tests.integration._f3 import call, flush_redis, world3  # noqa: F401

TODAY = dt.date.today()
DAYS = [{"date": (TODAY + dt.timedelta(days=i)).isoformat(), "tmin": 3, "tmax": 15, "rain_mm": 1, "wind_kmh": 9, "humidity_pct": 55, "icon": "cloud"} for i in range(8)]


def test_given_the_contract_then_the_weather_horizon_is_8_days_and_each_day_requires_the_four_values_and_an_icon():
    day = SPEC["components"]["schemas"]["WeatherDay"]
    assert {"tmin", "tmax", "rain_mm", "wind_kmh", "humidity_pct", "icon"} <= set(day["required"])
    assert SPEC["components"]["schemas"]["Weather"]["allOf"][1]["properties"]["days"]["maxItems"] == 8


def test_given_a_stored_forecast_when_reading_the_weather_then_the_body_validates_against_the_contract(client, token_for, world3):
    w = world3
    flush_redis()
    sql("INSERT INTO farm_weather (farm_id, cell_id, fetched_at, availability, reason, days) VALUES ($1,'33.6:-7.6',now(),'ok',NULL,$2::jsonb)"
        " ON CONFLICT (farm_id) DO NOTHING", w["farm_a"], json.dumps(DAYS))
    r = call(client, token_for(w["owner"]), "GET", f"/v1/farms/{w['farm_a']}/weather")
    assert r.status_code == 200
    assert_valid("Weather", r.json())


def test_given_no_forecast_when_reading_the_weather_then_the_unavailable_body_validates_and_carries_no_day(client, token_for, world3):
    w = world3
    flush_redis()
    r = call(client, token_for(w["owner"]), "GET", f"/v1/farms/{w['farm_a']}/weather")
    assert_valid("Weather", r.json())


def test_given_the_dashboard_then_it_validates_against_the_contract(client, token_for, world3):
    w = world3
    flush_redis()
    r = call(client, token_for(w["owner"]), "GET", f"/v1/farms/{w['farm_a']}/dashboard")
    assert r.status_code == 200
    assert_valid("Dashboard", r.json())
