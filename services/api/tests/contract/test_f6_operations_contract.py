"""T034 - POST/GET /v1/farms/{farm_id}/operations conform to contracts/openapi.yaml (schemas and status codes)."""
import uuid

from tests.contract._f6_spec import SCHEMAS, codes
from tests.helpers import auth
from tests.integration._f6 import op_body, world  # noqa: F401

LIST = "/v1/farms/{farm_id}/operations"
ONE = "/v1/farms/{farm_id}/operations/{operation_id}"


def test_given_the_contract_then_the_documented_codes_cover_creation_and_the_input_schema_is_closed():
    assert {"201", "413", "422"} <= codes(LIST, "post") and "200" in codes(LIST, "get")
    assert {"200", "404"} <= codes(ONE, "get")
    props = SCHEMAS["OperationInput"]["properties"]
    assert {"id", "type", "performed_on", "parcel_ids"} <= set(props) and SCHEMAS["OperationInput"].get("required")
    assert set(SCHEMAS["OperationInput"]["required"]) == {"id", "type", "performed_on", "parcel_ids"}


def test_given_a_valid_body_when_creating_then_201_with_the_documented_fields(client, token_for, world):
    w = world
    r = client.post(f"/v1/farms/{w['farm_a']}/operations", headers=auth(token_for(w["owner"])), json=op_body([w["a1"]]))
    assert r.status_code == 201, r.text
    assert {"id", "type", "performed_on", "status", "author_id", "parcels", "warnings", "overdue"} <= set(r.json())
    assert "label_photo_key" not in r.json() and "file_keys" not in r.json()
    assert r.json()["status"] in SCHEMAS["OperationInput"]["properties"]["status"]["enum"]


def test_given_each_documented_error_when_calling_then_the_status_code_matches(client, token_for, world):
    w = world
    h = auth(token_for(w["owner"]))
    base = f"/v1/farms/{w['farm_a']}/operations"
    assert client.post(base, headers=h, json={**op_body([w["a1"]]), "type": "bogus"}).status_code == 422
    assert client.post(base, headers=h, json=op_body([uuid.uuid4() for _ in range(51)])).status_code in (413, 422)
    assert client.get(f"{base}/{uuid.uuid4()}", headers=h).status_code == 404
    assert client.get(base).status_code == 401
    assert client.get(f"/v1/farms/{uuid.uuid4()}/operations", headers=h).status_code == 404


def test_given_a_listing_then_the_page_has_items_and_next_cursor_and_respects_the_documented_limit(client, token_for, world):
    w = world
    h = auth(token_for(w["owner"]))
    page = client.get(f"/v1/farms/{w['farm_a']}/operations", headers=h, params={"limit": 200})
    assert page.status_code == 200 and set(page.json()) == {"items", "next_cursor"}
    assert client.get(f"/v1/farms/{w['farm_a']}/operations", headers=h, params={"limit": 201}).status_code == 422
