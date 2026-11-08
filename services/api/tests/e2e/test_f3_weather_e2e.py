"""T043 - R1-A1, R1-A2 on the running stack: today + 7 days with the four values and icons; stale data keeps its date; unconfigured gateways read as unavailable."""
import uuid

from tests.e2e._f3 import client, day, run_job, seed_forecast, setup_farm
from tests.helpers import sql


def test_given_a_located_farm_when_opening_the_dashboard_then_today_and_7_days_show_with_temperature_rain_wind_humidity_and_icon():
    with client() as c:
        s = setup_farm(c, 2)
        seed_forecast(s["farm"], [day(i) for i in range(-1, 9)])
        w = c.get(f"/farms/{s['farm']}/dashboard", headers=s["oh"]).json()["weather"]
        assert w["availability"] == "ok" and [d["date"] for d in w["days"]] == [day(i)["date"] for i in range(8)]
        assert all({"tmin", "tmax", "rain_mm", "wind_kmh", "humidity_pct", "icon"} <= set(d) for d in w["days"])


def test_given_data_loaded_30_hours_ago_when_opening_the_dashboard_then_it_shows_the_last_data_with_its_date_as_stale():
    with client() as c:
        s = setup_farm(c, 1)
        seed_forecast(s["farm"], [day(i) for i in range(8)], age_h=30)
        w = c.get(f"/farms/{s['farm']}/weather", headers=s["oh"]).json()
        assert w["availability"] == "stale" and w["fetched_at"] and len(w["days"]) == 8


def test_given_empty_gateways_when_the_worker_refreshes_then_the_last_forecast_stays_dated_and_is_marked_unavailable_with_no_invented_value():
    with client() as c:
        s = setup_farm(c, 1)
        seed_forecast(s["farm"], [day(i) for i in range(8)], age_h=5)
        run_job("refresh_weather")
        w = c.get(f"/farms/{s['farm']}/weather", headers=s["oh"]).json()
        assert w["availability"] == "unavailable" and w["reason"] == "gateway_not_configured"
        assert len(w["days"]) == 8 and w["fetched_at"]


def test_given_a_farm_without_location_when_opening_the_weather_then_it_asks_to_set_the_location():
    with client() as c:
        s = setup_farm(c, 1)
        sql("UPDATE farms SET location = NULL WHERE id = $1", uuid.UUID(s["farm"]))
        w = c.get(f"/farms/{s['farm']}/weather", headers=s["oh"]).json()
        assert w["availability"] == "unavailable" and w["reason"] == "farm_not_located" and not w.get("days")


def test_given_a_farm_without_parcel_when_opening_the_dashboard_then_the_weather_shows_and_the_list_is_empty():
    with client() as c:
        s = setup_farm(c, 0)
        seed_forecast(s["farm"], [day(i) for i in range(8)])
        b = c.get(f"/farms/{s['farm']}/dashboard", headers=s["oh"]).json()
        assert b["parcels"] == [] and len(b["weather"]["days"]) == 8
