"""T075 - validate, correct and corrections conform to the contract (R7)."""
import uuid

from tests.contract._f6_spec import PATHS, SCHEMAS, codes
from tests.helpers import auth, sql
from tests.integration._f6 import add_operation, world  # noqa: F401

OP = "/v1/farms/{farm_id}/operations/{operation_id}"


def test_given_the_contract_then_validate_correct_and_corrections_document_their_error_codes():
    assert {"200", "401", "403", "404", "409"} <= codes(OP + "/validate", "post")
    assert {"200", "401", "403", "404", "409", "422"} <= codes(OP, "patch")
    assert {"200", "401", "403", "404"} <= codes(OP + "/corrections", "get")


def test_given_the_contract_then_a_correction_item_carries_author_date_before_and_after():
    props = SCHEMAS["Correction"]["properties"]
    assert {"id", "field", "before", "after", "author_id", "corrected_at", "source"} <= set(props)
    assert props["source"]["enum"] == ["manual", "sync_conflict"]
    items = PATHS[OP + "/corrections"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]["properties"]["items"]
    assert items["items"]["$ref"].endswith("/Correction")


def test_given_the_routes_then_the_documented_status_codes_hold(client, token_for, world):
    w = world
    oid = add_operation(w["farm_a"], w["worker"], w["a1"], status="pending_validation")
    f, m = f"/v1/farms/{w['farm_a']}/operations/{oid}", auth(token_for(w["manager"]))
    assert client.post(f"{f}/validate", headers=auth(token_for(w["worker"]))).status_code == 403
    assert client.post(f"/v1/farms/{w['farm_a']}/operations/{uuid.uuid4()}/validate", headers=m).status_code == 404
    assert client.post(f"{f}/validate").status_code == 401
    ok = client.post(f"{f}/validate", headers=m)
    assert ok.status_code == 200 and ok.json()["status"] == "validated"
    assert client.post(f"{f}/validate", headers=m).status_code == 409
    assert client.patch(f, headers=m, json={"dose": -1}).status_code == 422
    assert client.patch(f, headers=m, json={"note": "x" * 501}).status_code == 422
    cancelled = add_operation(w["farm_a"], w["worker"], w["a1"], status="cancelled")
    assert client.patch(f"/v1/farms/{w['farm_a']}/operations/{cancelled}", headers=m, json={"note": "n"}).status_code == 409
    sql("SELECT 1")
    listing = client.get(f"{f}/corrections", headers=m)
    assert listing.status_code == 200 and set(listing.json()) == {"items"}
