"""T066 - POST /v1/farms/{farm_id}/operations/parse conforms to the contract (R5)."""
from tests.contract._f6_spec import PATHS, SCHEMAS, codes
from tests.helpers import auth
from tests.integration._f6 import world  # noqa: F401

PARSE = "/v1/farms/{farm_id}/operations/parse"


def test_given_the_contract_then_parse_documents_its_error_codes_and_a_strict_text_only_body():
    assert {"200", "401", "404", "422", "429", "503"} <= codes(PARSE, "post")
    body = PATHS[PARSE]["post"]["requestBody"]["content"]["application/json"]["schema"]
    ref = body["$ref"].rsplit("/", 1)[1] if "$ref" in body else None
    schema = SCHEMAS[ref] if ref else body
    assert schema["additionalProperties"] is False and schema["required"] == ["text"]
    assert schema["properties"]["text"]["maxLength"] == 500 and set(schema["properties"]) == {"text"}


def test_given_the_contract_then_the_200_response_has_the_draft_shape():
    ok = PATHS[PARSE]["post"]["responses"]["200"]["content"]["application/json"]["schema"]
    schema = SCHEMAS[ok["$ref"].rsplit("/", 1)[1]] if "$ref" in ok else ok
    assert {"understood", "requires_confirmation", "draft", "ambiguous"} <= set(schema["properties"])


def test_given_no_nlu_url_then_the_503_body_matches_the_contract(client, token_for, world, monkeypatch):
    monkeypatch.setenv("AYLAL_NLU_URL", "")
    r = client.post(f"/v1/farms/{world['farm_a']}/operations/parse", headers=auth(token_for(world["owner"])), json={"text": "x"})
    assert r.status_code == 503 and r.json() == {"code": "parse_unavailable"}
