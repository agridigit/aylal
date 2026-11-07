"""T055 - GET /v1/farms/{farm_id}/fields/{field_id}/earliest-harvest conforms to the contract."""
import uuid

from tests.contract._f6_spec import codes
from tests.helpers import auth
from tests.integration._f6 import world  # noqa: F401

ROUTE = "/v1/farms/{farm_id}/fields/{field_id}/earliest-harvest"


def test_given_the_contract_then_200_and_404_are_documented():
    assert {"200", "404"} <= codes(ROUTE, "get")


def test_given_a_parcel_without_treatment_then_the_documented_body_is_returned(client, token_for, world):
    w = world
    r = client.get(f"/v1/farms/{w['farm_a']}/fields/{w['a1']}/earliest-harvest", headers=auth(token_for(w["owner"])))
    assert r.status_code == 200, r.text
    assert r.json() == {"date": None, "harvestable_now": True, "unknown_dar": False, "limiting_product": None}


def test_given_an_unknown_parcel_or_a_non_member_then_the_documented_404_has_the_same_body(client, token_for, world):
    w = world
    a = client.get(f"/v1/farms/{w['farm_a']}/fields/{uuid.uuid4()}/earliest-harvest", headers=auth(token_for(w["owner"])))
    b = client.get(f"/v1/farms/{w['farm_a']}/fields/{w['a1']}/earliest-harvest", headers=auth(token_for(w["outsider"])))
    assert a.status_code == b.status_code == 404 and a.json() == b.json()
