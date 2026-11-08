"""T049 - alert responses honour the contract; dismissal is staff only."""
from tests.contract._f3_schema import SPEC, assert_valid
from tests.integration._f3 import call, seed_alert, world3  # noqa: F401


def test_given_the_contract_then_an_alert_requires_parcel_type_severity_source_and_status():
    assert {"parcel_id", "type", "severity", "source", "status"} <= set(SPEC["components"]["schemas"]["Alert"]["required"])
    assert SPEC["paths"]["/farms/{farm_id}/alerts/{alert_id}/dismiss"]["post"]["x-action"] == "alert.dismiss"


def test_given_alerts_of_every_type_when_listing_then_each_validates_against_the_contract(client, token_for, world3):
    w = world3
    for t in ("frost", "chergui", "heavy_rain", "strong_wind"):
        seed_alert(w["farm_a"], w["a1"], type_=t, severity="warning")
    body = call(client, token_for(w["owner"]), "GET", f"/v1/farms/{w['farm_a']}/alerts").json()
    assert body
    for a in body:
        assert_valid("Alert", a)


def test_given_a_dismissal_then_the_response_validates_against_the_contract(client, token_for, world3):
    w = world3
    a = seed_alert(w["farm_a"], w["a1"])
    r = call(client, token_for(w["owner"]), "POST", f"/v1/farms/{w['farm_a']}/alerts/{a}/dismiss")
    assert r.status_code == 200
    assert_valid("Alert", r.json())
