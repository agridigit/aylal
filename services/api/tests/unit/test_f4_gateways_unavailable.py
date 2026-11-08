"""T011 - G5: empty/unlisted/mute gateways -> unavailable + reason, never an invented, interpolated or default value."""
import datetime as dt

import pytest

NOW = dt.datetime(2026, 6, 4, 12, 0, tzinfo=dt.UTC)
OBS = {"days": [{"date": "2026-06-02", "rain_mm": 3.0}, {"date": "2026-06-03", "rain_mm": 0.0}]}
VALUE_FIELDS = {"days", "rain_mm", "et0_mm", "rain"}


class Spy:
    def __init__(self, response=None, error=None):
        self.calls, self.response, self.error = [], response, error

    def __call__(self, method, url, params=None, json=None):
        self.calls.append((method, url, params, json))
        if self.error:
            raise self.error
        return self.response


def _gw(url, hosts, spy):
    from app.monitoring.gateways import ObservedWeatherGateway

    return ObservedWeatherGateway(url=url, allowed_hosts=hosts, http=spy)


def _assert_unavailable(res, reason):
    assert res["availability"] == "unavailable" and res["reason"] == reason
    assert not (set(res) & VALUE_FIELDS), f"invented value fields: {set(res) & VALUE_FIELDS}"


def test_given_an_empty_observed_url_then_unavailable_not_configured_and_zero_calls():
    spy = Spy()
    _assert_unavailable(_gw("", (), spy).fetch(lat_r=33.6, lon_r=-7.6, date_from="2026-06-01", date_to="2026-06-03"), "gateway_not_configured")
    assert spy.calls == []


def test_given_a_host_outside_the_allow_list_then_unavailable_and_zero_calls():
    spy = Spy()
    _assert_unavailable(_gw("https://evil.example.com/o", ("obs.example.ma",), spy).fetch(lat_r=33.6, lon_r=-7.6, date_from="2026-06-01", date_to="2026-06-03"), "gateway_not_configured")
    assert spy.calls == []


def test_given_an_unreachable_gateway_then_unavailable_gateway_unreachable_without_a_default_value():
    spy = Spy(error=OSError("down"))
    _assert_unavailable(_gw("https://obs.example.ma/r", ("obs.example.ma",), spy).fetch(lat_r=33.6, lon_r=-7.6, date_from="2026-06-01", date_to="2026-06-03"), "gateway_unreachable")


def test_given_a_window_longer_than_7_days_then_no_call_is_made():
    spy = Spy(response=OBS)
    with pytest.raises(ValueError):
        _gw("https://obs.example.ma/r", ("obs.example.ma",), spy).fetch(lat_r=33.6, lon_r=-7.6, date_from="2026-05-20", date_to="2026-06-03")
    assert spy.calls == []


def test_given_a_configured_gateway_when_it_answers_then_observed_rain_is_returned_as_is():
    spy = Spy(response=OBS)
    res = _gw("https://obs.example.ma/r", ("obs.example.ma",), spy).fetch(lat_r=33.6, lon_r=-7.6, date_from="2026-06-02", date_to="2026-06-03")
    assert res["availability"] == "ok" and res["days"] == OBS["days"] and len(spy.calls) == 1


def test_given_a_forecast_day_without_et0_then_it_is_still_valid_and_et0_is_never_filled_in():
    from app.monitoring.gateways import normalise_forecast_day

    day = normalise_forecast_day({"date": "2026-06-04", "tmin": 14, "tmax": 29, "rain_mm": 0, "wind_kmh": 8, "humidity_pct": 50, "code": 1})
    assert "et0_mm" not in day or day["et0_mm"] is None
    assert normalise_forecast_day({"date": "2026-06-04", "tmin": 14, "tmax": 29, "rain_mm": 0, "wind_kmh": 8, "humidity_pct": 50, "code": 1, "et0_mm": 4.5})["et0_mm"] == 4.5


def test_given_no_observed_rain_for_a_past_day_then_the_source_is_forecast_and_confidence_is_lowered():
    from app.irrigation.weather_input import rain_for_day

    res = rain_for_day(day="2026-06-03", observed=None, last_forecast={"rain_mm": 2.0})
    assert res["rain_source"] == "forecast" and res["rain_mm"] == 2.0 and res["confidence_factor"] == "rain_not_observed"
    both = rain_for_day(day="2026-06-03", observed={"rain_mm": 0.4}, last_forecast={"rain_mm": 2.0})
    assert both["rain_source"] == "observed" and both["rain_mm"] == 0.4


def test_given_neither_observation_nor_forecast_then_the_rain_is_unavailable_not_zero():
    from app.irrigation.weather_input import rain_for_day

    res = rain_for_day(day="2026-06-03", observed=None, last_forecast=None)
    assert res["rain_mm"] is None and res["availability"] == "unavailable"


@pytest.mark.parametrize("age_h,expected", [(24.0, "ok"), (24.1, "stale")])
def test_given_a_forecast_older_than_24_hours_then_it_is_stale_with_the_injected_clock(age_h, expected):
    from app.monitoring.gateways import weather_freshness

    assert weather_freshness(NOW - dt.timedelta(hours=age_h), NOW)["availability"] == expected
