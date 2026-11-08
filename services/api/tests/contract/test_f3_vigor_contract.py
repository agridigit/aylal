"""T056 - vigor responses honour the contract (clear_pct >= 80, <= 400 points, no technical index names)."""
from tests.contract._f3_schema import SPEC, assert_valid
from tests.integration._f3 import call, seed_scene, world3  # noqa: F401


def test_given_the_contract_then_published_points_are_at_least_80_percent_clear_and_capped_at_400():
    s = SPEC["components"]["schemas"]
    assert s["VigorPoint"]["properties"]["clear_pct"]["minimum"] == 80
    assert s["VigorSeries"]["properties"]["points"]["maxItems"] == 400
    assert "ndvi" not in str(s).lower() and "ndmi" not in str(s).lower()


def test_given_a_series_when_reading_then_the_body_validates_against_the_contract(client, token_for, world3):
    w = world3
    seed_scene(w["farm_a"], w["a1"])
    r = call(client, token_for(w["owner"]), "GET", f"/v1/farms/{w['farm_a']}/parcels/{w['a1']}/vigor")
    assert r.status_code == 200
    assert_valid("VigorSeries", r.json())


def test_given_a_scene_when_asking_the_map_then_a_signed_url_with_a_date_is_served_and_no_storage_key_leaks(client, token_for, world3):
    w = world3
    scene, _ = seed_scene(w["farm_a"], w["a1"])
    r = call(client, token_for(w["owner"]), "GET", f"/v1/farms/{w['farm_a']}/parcels/{w['a1']}/vigor/scenes/{scene}/map")
    assert r.status_code == 200
    b = r.json()
    assert {"url", "expires_at", "acquired_on"} <= set(b)
    assert "map_key" not in r.text and "raster_key" not in r.text


def test_given_a_parcel_without_history_when_comparing_then_reference_available_is_false_with_empty_curves(client, token_for, world3):
    w = world3
    b = call(client, token_for(w["owner"]), "GET", f"/v1/farms/{w['farm_a']}/parcels/{w['p'][6]}/vigor/compare").json()
    assert b["reference_available"] is False and not b.get("previous")
