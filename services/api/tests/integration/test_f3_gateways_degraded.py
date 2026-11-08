"""T024 - G5: without gateways the API answers 200 with an explicit unavailable/stale status, never an invented value."""
import asyncio
import datetime as dt
import json

import pytest

from tests.helpers import sql
from tests.integration._f3 import call, flush_redis, seed_scene, world3  # noqa: F401

DAYS = [{"date": (dt.date.today() + dt.timedelta(days=i)).isoformat(), "tmin": 3, "tmax": 15, "rain_mm": 1, "wind_kmh": 9, "humidity_pct": 55, "icon": "cloud"} for i in range(8)]


@pytest.fixture(autouse=True)
def _no_gateway(monkeypatch):
    for v in ("AYLAL_WEATHER_URL", "AYLAL_IMAGERY_URL", "AYLAL_PUSH_URL", "AYLAL_EXTERNAL_ALLOWED_HOSTS"):
        monkeypatch.delenv(v, raising=False)
    flush_redis()


def _weather_row(farm, *, age_h, availability="ok", reason=None, days=True):
    sql("INSERT INTO farm_weather (farm_id, cell_id, fetched_at, availability, reason, days) VALUES ($1,'33.6:-7.6',now() - $2 * interval '1 hour',$3,$4,$5::jsonb)",
        farm, age_h, availability, reason, json.dumps(DAYS if days else []))


def test_given_no_gateway_and_no_forecast_ever_then_weather_is_unavailable_with_a_reason_and_no_value(client, token_for, world3):
    w = world3
    sql("UPDATE farms SET location = ST_SetSRID(ST_MakePoint(-7.6, 33.57), 4326) WHERE id = $1", w["farm_a"])  # located: farm_not_located is another case
    r = call(client, token_for(w["owner"]), "GET", f"/v1/farms/{w['farm_a']}/weather")
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["availability"] == "unavailable" and b["reason"] == "gateway_not_configured"
    assert not b.get("days") and b.get("fetched_at") is None


def test_given_a_recent_forecast_then_it_is_served_as_is_with_its_date(client, token_for, world3):
    w = world3
    _weather_row(w["farm_a"], age_h=2)
    b = call(client, token_for(w["owner"]), "GET", f"/v1/farms/{w['farm_a']}/weather").json()
    assert b["availability"] == "ok" and b["days"] == DAYS and b["fetched_at"]


def test_given_a_forecast_older_than_24_hours_then_it_is_stale_but_kept_and_dated(client, token_for, world3):
    w = world3
    _weather_row(w["farm_a"], age_h=30)
    b = call(client, token_for(w["owner"]), "GET", f"/v1/farms/{w['farm_a']}/weather").json()
    assert b["availability"] == "stale" and b["reason"] == "stale" and b["days"] == DAYS and b["fetched_at"]


def test_given_an_unreachable_gateway_recorded_by_the_worker_then_the_reason_is_exposed_and_the_last_data_is_kept(client, token_for, world3):
    w = world3
    _weather_row(w["farm_a"], age_h=3, availability="unavailable", reason="gateway_unreachable")
    b = call(client, token_for(w["owner"]), "GET", f"/v1/farms/{w['farm_a']}/weather").json()
    assert b["availability"] == "unavailable" and b["reason"] == "gateway_unreachable" and b["days"] == DAYS


def test_given_no_gateway_then_the_dashboard_and_vigor_answer_200_with_unavailable_and_dated_history(client, token_for, world3):
    w = world3
    sql("UPDATE farms SET location = ST_SetSRID(ST_MakePoint(-7.6, 33.57), 4326) WHERE id = $1", w["farm_a"])  # located: farm_not_located is another case
    seed_scene(w["farm_a"], w["a1"])
    tok = token_for(w["owner"])
    d = call(client, tok, "GET", f"/v1/farms/{w['farm_a']}/dashboard")
    assert d.status_code == 200 and d.json()["weather"]["availability"] == "unavailable" and d.json()["weather"]["reason"] == "gateway_not_configured"
    v = call(client, tok, "GET", f"/v1/farms/{w['farm_a']}/parcels/{w['a1']}/vigor")
    assert v.status_code == 200 and v.json()["points"] and all(p["acquired_on"] for p in v.json()["points"])


def test_given_user_requests_then_no_gateway_call_is_ever_made(client, token_for, world3, monkeypatch):
    from app.monitoring import gateways

    w = world3
    _weather_row(w["farm_a"], age_h=1)
    seen = []

    def spy(*a, **k):
        seen.append(1)
        raise AssertionError("a user request must never call a gateway")

    for cls, name in ((gateways.WeatherGateway, "fetch"), (gateways.ImageryGateway, "scenes"), (gateways.PushGateway, "send")):
        monkeypatch.setattr(cls, name, spy)
    tok = token_for(w["owner"])
    f = f"/v1/farms/{w['farm_a']}"
    for path in ("dashboard", "weather", f"parcels/{w['a1']}/vigor", "alerts", "zones", "summary/today"):
        assert call(client, tok, "GET", f"{f}/{path}").status_code == 200, path
    assert seen == []


def test_given_a_cell_slot_then_only_one_call_per_01_degree_cell_and_3_hours(world3):
    from app.monitoring.gateways import acquire_cell_slot

    async def go():
        t0 = dt.datetime(2026, 12, 5, 6, 0, tzinfo=dt.UTC)
        return [await acquire_cell_slot("33.6:-7.6", t0), await acquire_cell_slot("33.6:-7.6", t0 + dt.timedelta(hours=2, minutes=59)),
                await acquire_cell_slot("33.7:-7.6", t0), await acquire_cell_slot("33.6:-7.6", t0 + dt.timedelta(hours=3, minutes=1))]

    assert asyncio.run(go()) == [True, False, True, True]


def test_given_a_daily_budget_then_calls_beyond_it_are_refused(world3):
    from app.monitoring.gateways import acquire_daily_budget

    async def go():
        day = dt.date(2026, 12, 5)
        return [await acquire_daily_budget("weather", 2, day) for _ in range(3)] + [await acquire_daily_budget("weather", 2, day + dt.timedelta(days=1))]

    assert asyncio.run(go()) == [True, True, False, True]
