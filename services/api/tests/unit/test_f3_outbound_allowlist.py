"""T011 - G5: outbound requests carry exact allow-listed keys; nothing personal or exact leaves Morocco."""
import pytest

FORBIDDEN = ("farm_id", "user_id", "parcel_id", "name", "phone", "phone_e164", "geometry", "polygon", "lat_exact", "owner")


def test_given_a_farm_position_then_the_weather_request_is_rounded_to_0_1_degree_with_exact_keys():
    from app.monitoring.gateways import build_weather_request

    req = build_weather_request(lat=33.5731, lon=-7.5898)
    assert set(req) == {"lat", "lon", "days"}
    assert (req["lat"], req["lon"], req["days"]) == (33.6, -7.6, 8)


def test_given_an_imagery_request_then_only_a_mgrs_tile_and_dates_are_sent():
    from app.monitoring.gateways import build_imagery_request

    req = build_imagery_request(mgrs="31SBU", date_from="2026-11-01", date_to="2026-12-01")
    assert req == {"path": "/tiles/31SBU/scenes", "params": {"from": "2026-11-01", "to": "2026-12-01"}}


@pytest.mark.parametrize("bad", ["", "not a tile", "11111111-1111-4111-8111-111111111111", "31SBU/../x"])
def test_given_something_that_is_not_a_mgrs_tile_then_the_imagery_request_is_refused(bad):
    from app.monitoring.gateways import build_imagery_request

    with pytest.raises(ValueError):
        build_imagery_request(mgrs=bad, date_from="2026-11-01", date_to="2026-12-01")


def test_given_a_push_then_the_payload_has_exactly_token_alert_and_locale():
    from app.monitoring.gateways import build_push_payload

    p = build_push_payload(device_token="tok", alert_id="0b0c6c9e-0000-4000-8000-000000000000", locale="ary")
    assert set(p) == {"device_token", "alert_id", "locale"}


def test_given_the_allow_list_then_it_lists_exact_keys_per_gateway():
    from app.monitoring.gateways import OUTBOUND_ALLOWLIST

    assert OUTBOUND_ALLOWLIST["weather"] == frozenset({"lat", "lon", "days"})
    assert OUTBOUND_ALLOWLIST["push"] == frozenset({"device_token", "alert_id", "locale"})
    assert OUTBOUND_ALLOWLIST["imagery"] == frozenset({"mgrs", "from", "to"})


@pytest.mark.parametrize("kind", ["weather", "imagery", "push"])
@pytest.mark.parametrize("extra", FORBIDDEN)
def test_given_any_personal_or_exact_field_then_the_outbound_guard_refuses_it(kind, extra):
    from app.monitoring.gateways import OUTBOUND_ALLOWLIST, assert_outbound

    ok = {k: "x" for k in OUTBOUND_ALLOWLIST[kind]}
    assert_outbound(kind, ok)
    with pytest.raises(ValueError):
        assert_outbound(kind, {**ok, extra: "x"})


def test_given_a_missing_key_then_the_guard_also_refuses_so_keys_are_exact():
    from app.monitoring.gateways import assert_outbound

    with pytest.raises(ValueError):
        assert_outbound("push", {"device_token": "t", "alert_id": "a"})
