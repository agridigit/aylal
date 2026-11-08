"""T012 - G5: outbound requests carry exact allow-listed keys; the F4 observed-rain request leaks nothing personal or exact."""
import pytest

FORBIDDEN = ("farm_id", "user_id", "parcel_id", "name", "phone", "phone_e164", "geometry", "polygon", "lat_exact", "owner", "season_id", "event_id")


def test_given_the_allow_list_then_weather_observed_has_the_exact_four_keys_and_weather_is_unchanged():
    from app.monitoring.gateways import OUTBOUND_ALLOWLIST

    assert OUTBOUND_ALLOWLIST["weather_observed"] == frozenset({"lat", "lon", "from", "to"})
    assert OUTBOUND_ALLOWLIST["weather"] == frozenset({"lat", "lon", "days"})


def test_given_a_farm_position_then_the_observed_request_is_rounded_to_0_1_degree_with_exact_keys():
    from app.monitoring.gateways import build_weather_observed_request

    req = build_weather_observed_request(lat=33.5731, lon=-7.5898, date_from="2026-06-01", date_to="2026-06-03")
    assert set(req) == {"lat", "lon", "from", "to"}
    assert (req["lat"], req["lon"], req["from"], req["to"]) == (33.6, -7.6, "2026-06-01", "2026-06-03")


def test_given_a_window_over_7_days_then_the_request_is_refused():
    from app.monitoring.gateways import build_weather_observed_request

    with pytest.raises(ValueError):
        build_weather_observed_request(lat=33.6, lon=-7.6, date_from="2026-05-20", date_to="2026-06-03")


@pytest.mark.parametrize("extra", FORBIDDEN)
def test_given_any_personal_or_exact_field_then_the_outbound_guard_refuses_it(extra):
    from app.monitoring.gateways import OUTBOUND_ALLOWLIST, assert_outbound

    ok = {k: "x" for k in OUTBOUND_ALLOWLIST["weather_observed"]}
    assert_outbound("weather_observed", ok)
    with pytest.raises(ValueError):
        assert_outbound("weather_observed", {**ok, extra: "x"})


def test_given_a_missing_key_then_the_guard_refuses_so_keys_are_exact():
    from app.monitoring.gateways import assert_outbound

    with pytest.raises(ValueError):
        assert_outbound("weather_observed", {"lat": 33.6, "lon": -7.6, "from": "2026-06-01"})
