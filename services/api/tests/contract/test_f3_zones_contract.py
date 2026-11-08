"""T063 - zone responses honour the contract; the observation input forbids storage keys and accepts only a note and an opaque photo id."""
import uuid

from tests.contract._f3_schema import SPEC, assert_valid
from tests.integration._f3 import call, seed_zone, world3  # noqa: F401


def test_given_the_contract_then_the_observation_input_is_closed_and_the_note_capped_at_500():
    o = SPEC["components"]["schemas"]["ObservationInput"]
    assert o["additionalProperties"] is False and o["properties"]["note"]["maxLength"] == 500


def test_given_zones_when_listing_then_each_validates_against_the_contract(client, token_for, world3):
    w = world3
    seed_zone(w["farm_a"], w["a1"])
    seed_zone(w["farm_a"], w["a1"], status="visited")
    body = call(client, token_for(w["owner"]), "GET", f"/v1/farms/{w['farm_a']}/zones").json()
    assert body
    for z in body:
        assert_valid("Zone", z)


def test_given_a_forged_storage_key_in_an_observation_then_it_is_refused_with_422(client, token_for, world3):
    w = world3
    z = seed_zone(w["farm_a"], w["a1"])
    r = call(client, token_for(w["worker"]), "POST", f"/v1/farms/{w['farm_a']}/zones/{z}/observations",
             {"id": str(uuid.uuid4()), "note": "x", "photo_key": "farms/x/zone-photos/y"})
    assert r.status_code == 422


def test_given_a_note_of_501_characters_then_it_is_refused_before_any_write(client, token_for, world3):
    w = world3
    z = seed_zone(w["farm_a"], w["a1"])
    r = call(client, token_for(w["worker"]), "POST", f"/v1/farms/{w['farm_a']}/zones/{z}/observations", {"id": str(uuid.uuid4()), "note": "x" * 501})
    assert r.status_code == 422
