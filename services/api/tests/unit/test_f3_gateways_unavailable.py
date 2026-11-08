"""T010 - G5: no URL or unlisted host -> unavailable, never an invented value; the spy proves zero network calls."""
import datetime as dt

import pytest

NOW = dt.datetime(2026, 12, 5, 12, 0, tzinfo=dt.UTC)
DAYS = [{"date": f"2026-12-{5 + i:02d}", "tmin": 3, "tmax": 15, "rain_mm": 1, "wind_kmh": 9, "humidity_pct": 55, "code": 3} for i in range(8)]
VALUE_FIELDS = {"days", "tmin", "tmax", "rain_mm", "wind_kmh", "humidity_pct", "scenes"}


class Spy:
    def __init__(self, response=None, error=None):
        self.calls, self.response, self.error = [], response, error

    def __call__(self, method, url, params=None, json=None):
        self.calls.append((method, url, params, json))
        if self.error:
            raise self.error
        return self.response


def _gw(url, hosts, spy):
    from app.monitoring.gateways import WeatherGateway

    return WeatherGateway(url=url, allowed_hosts=hosts, http=spy)


def _assert_unavailable(res, reason):
    assert res["availability"] == "unavailable" and res["reason"] == reason
    assert not (set(res) & VALUE_FIELDS), f"invented value fields: {set(res) & VALUE_FIELDS}"


def test_given_an_empty_url_when_fetching_weather_then_unavailable_not_configured_and_zero_calls():
    spy = Spy()
    _assert_unavailable(_gw("", (), spy).fetch(lat_r=33.6, lon_r=-7.6), "gateway_not_configured")
    assert spy.calls == []


def test_given_a_host_outside_the_allow_list_when_fetching_then_unavailable_and_zero_calls():
    spy = Spy()
    _assert_unavailable(_gw("https://evil.example.com/w", ("meteo.example.ma",), spy).fetch(lat_r=33.6, lon_r=-7.6), "gateway_not_configured")
    assert spy.calls == []


def test_given_an_unreachable_gateway_then_unavailable_with_gateway_unreachable_and_no_default_value():
    spy = Spy(error=OSError("down"))
    _assert_unavailable(_gw("https://meteo.example.ma/f", ("meteo.example.ma",), spy).fetch(lat_r=33.6, lon_r=-7.6), "gateway_unreachable")
    assert len(spy.calls) == 1


def test_given_a_malformed_answer_then_unavailable_and_nothing_is_interpolated():
    spy = Spy(response={"days": DAYS[:3]})  # not 8 days
    _assert_unavailable(_gw("https://meteo.example.ma/f", ("meteo.example.ma",), spy).fetch(lat_r=33.6, lon_r=-7.6), "gateway_unreachable")


def test_given_a_configured_gateway_when_it_answers_then_the_8_days_are_returned_as_is():
    spy = Spy(response={"days": DAYS})
    res = _gw("https://meteo.example.ma/f", ("meteo.example.ma",), spy).fetch(lat_r=33.6, lon_r=-7.6)
    assert res["availability"] == "ok" and res["days"] == DAYS
    assert len(spy.calls) == 1


@pytest.mark.parametrize("age_h,expected", [(23.9, "ok"), (24.0, "ok"), (24.1, "stale"), (72, "stale")])
def test_given_a_forecast_older_than_24_hours_then_it_is_stale(age_h, expected):
    from app.monitoring.gateways import weather_freshness

    res = weather_freshness(NOW - dt.timedelta(hours=age_h), NOW)
    assert res["availability"] == expected
    assert res.get("reason") == ("stale" if expected == "stale" else None)


def test_given_no_forecast_ever_fetched_then_freshness_is_unavailable_without_values():
    from app.monitoring.gateways import weather_freshness

    _assert_unavailable(weather_freshness(None, NOW), "gateway_not_configured")


def test_given_the_push_gateway_not_configured_then_unavailable_and_zero_calls():
    from app.monitoring.gateways import PushGateway

    spy = Spy()
    res = PushGateway(url="", allowed_hosts=(), http=spy).send(device_token="tok", alert_id="a", locale="fr")
    assert res["availability"] == "unavailable" and res["reason"] == "gateway_not_configured" and spy.calls == []


def test_given_the_imagery_gateway_not_configured_then_no_scene_and_zero_calls():
    from app.monitoring.gateways import ImageryGateway

    spy = Spy()
    res = ImageryGateway(url="", allowed_hosts=(), http=spy).scenes(mgrs="31SBU", date_from="2026-11-01", date_to="2026-12-01")
    _assert_unavailable(res, "gateway_not_configured")
    assert spy.calls == []
