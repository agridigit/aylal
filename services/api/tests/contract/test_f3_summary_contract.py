"""T080 - the daily summary and its settings honour the contract: only red and orange parcels, capped, hour bounded, 422 documented."""
from tests.contract._f3_schema import SPEC, assert_valid
from tests.integration._f3 import call, world3  # noqa: F401

SETTINGS = "/farms/{farm_id}/summary/settings"


def test_given_the_contract_then_the_summary_lists_only_red_and_orange_parcels_capped_at_100():
    items = SPEC["components"]["schemas"]["Summary"]["properties"]["items"]
    assert items["maxItems"] == 100
    assert set(items["items"]["properties"]["color"]["enum"]) == {"red", "orange"}
    assert set(items["items"]["required"]) == {"parcel_id", "color", "reason_key"}


def test_given_the_contract_then_the_settings_hour_is_bounded_and_422_is_documented():
    put = SPEC["paths"][SETTINGS]["put"]
    body = put["requestBody"]["content"]["application/json"]["schema"]
    assert (body["properties"]["summary_hour"]["minimum"], body["properties"]["summary_hour"]["maximum"]) == (0, 23)
    assert "422" in put["responses"] and "404" in put["responses"]


def test_given_a_worker_when_reading_the_summary_then_the_body_validates(client, token_for, world3):
    w = world3
    r = call(client, token_for(w["worker"]), "GET", f"/v1/farms/{w['farm_a']}/summary/today")
    assert r.status_code == 200
    assert_valid("Summary", r.json())
