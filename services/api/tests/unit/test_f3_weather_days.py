"""T040 - R1-A1, R1-A2: the weather window is today + 7 days with the four values and an icon; nothing is padded or invented."""
import datetime as dt

from app.monitoring.gateways import weather_freshness
from app.monitoring.weather import today_plus_seven

TODAY = dt.date(2026, 12, 5)


def _day(offset, **over):
    d = {"date": (TODAY + dt.timedelta(days=offset)).isoformat(), "tmin": 5.0, "tmax": 18.0, "rain_mm": 0.0, "wind_kmh": 12.0, "humidity_pct": 55.0, "icon": "sun"}
    return {**d, **over}


def test_given_a_long_forecast_when_shaping_then_today_and_the_7_next_days_are_kept_in_order():
    days = today_plus_seven([_day(i) for i in (9, 3, 0, 1, 2, 4, 5, 6, 7, 8)], TODAY)
    assert [d["date"] for d in days] == [(TODAY + dt.timedelta(days=i)).isoformat() for i in range(8)]


def test_given_days_in_the_past_when_shaping_then_they_are_dropped():
    days = today_plus_seven([_day(-2), _day(-1), _day(0)], TODAY)
    assert [d["date"] for d in days] == [TODAY.isoformat()]


def test_given_each_day_when_shaping_then_temperature_rain_wind_humidity_and_icon_are_present():
    d = today_plus_seven([_day(0)], TODAY)[0]
    assert {"date", "tmin", "tmax", "rain_mm", "wind_kmh", "humidity_pct", "icon"} <= set(d)
    assert d["icon"] == "sun"


def test_given_a_gateway_code_when_shaping_then_it_is_served_as_an_icon_string():
    d = today_plus_seven([{**_day(0), "icon": None, "icon_code": 3}], TODAY)[0]
    assert isinstance(d["icon"], str) and d["icon"] != ""


def test_given_a_short_forecast_when_shaping_then_nothing_is_padded_or_interpolated():
    assert len(today_plus_seven([_day(0), _day(3)], TODAY)) == 2


def test_given_a_day_without_a_value_when_shaping_then_the_day_is_dropped_rather_than_filled_with_zero():
    broken = {k: v for k, v in _day(1).items() if k != "rain_mm"}
    assert [d["date"] for d in today_plus_seven([_day(0), broken], TODAY)] == [TODAY.isoformat()]


def test_given_no_days_when_shaping_then_the_list_is_empty():
    assert today_plus_seven([], TODAY) == []


def test_given_data_older_than_24_hours_then_it_is_stale_and_exactly_24_hours_is_not():
    now = dt.datetime(2026, 12, 5, 12, tzinfo=dt.UTC)
    assert weather_freshness(now - dt.timedelta(hours=25), now)["availability"] == "stale"
    assert weather_freshness(now - dt.timedelta(hours=24), now)["availability"] == "ok"
