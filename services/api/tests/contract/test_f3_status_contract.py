"""T070 - status responses honour the contract: colour, one-sentence reason key, contributors with their source."""
from tests.contract._f3_schema import SPEC, assert_valid
from tests.integration._f3 import call, seed_status_item, world3  # noqa: F401


def test_given_the_contract_then_a_contributor_names_its_source_among_the_five_known_ones():
    item = SPEC["components"]["schemas"]["StatusItem"]
    assert set(item["properties"]["source"]["enum"]) == {"weather_alert", "vigor_anomaly", "overdue_operations", "irrigation_need", "health_risk"}
    assert set(SPEC["components"]["schemas"]["ParcelStatus"]["properties"]["color"]["enum"]) == {"green", "orange", "red"}


def test_given_a_parcel_with_contributors_when_reading_its_status_then_the_body_validates_against_the_contract(client, token_for, world3):
    w = world3
    seed_status_item(w["farm_a"], w["a1"], source="weather_alert")
    r = call(client, token_for(w["owner"]), "GET", f"/v1/farms/{w['farm_a']}/parcels/{w['a1']}/status")
    assert r.status_code == 200
    assert_valid("ParcelStatus", r.json())


def test_given_the_dashboard_then_every_parcel_entry_validates_and_the_list_is_capped_at_100(client, token_for, world3):
    w = world3
    b = call(client, token_for(w["owner"]), "GET", f"/v1/farms/{w['farm_a']}/dashboard").json()
    assert len(b["parcels"]) <= 100
    for p in b["parcels"]:
        assert_valid("ParcelStatus", p)
