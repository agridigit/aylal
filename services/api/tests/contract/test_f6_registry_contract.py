"""T071 - the registry and export routes conform to the contract (R6)."""
from tests.contract._f6_spec import SCHEMAS, codes
from tests.helpers import auth
from tests.integration._f6 import add_operation, add_registry, world  # noqa: F401
from tests.integration._f6_export import EXPORT, add_job

EXPORTS = "/v1/farms/{farm_id}/registry/exports"
JOB = "/v1/farms/{farm_id}/registry/exports/{job_id}"


def test_given_the_contract_then_the_export_routes_document_their_error_codes():
    assert {"202", "401", "403", "404", "409", "422", "429"} <= codes(EXPORTS, "post")
    assert {"200", "401", "403", "404", "410"} <= codes(JOB, "get")
    assert {"200", "403"} <= codes("/v1/farms/{farm_id}/registry", "get")


def test_given_the_contract_then_the_export_request_is_strict_and_has_no_object_key():
    schema = SCHEMAS["RegistryExportRequest"]
    assert schema["additionalProperties"] is False
    assert set(schema["properties"]) == {"period_from", "period_to", "format", "scope", "lang", "parcel_id"}
    assert set(schema["required"]) == {"period_from", "period_to", "format", "scope", "lang"}
    assert schema["properties"]["format"]["enum"] == ["pdf", "xlsx", "both"] and schema["properties"]["lang"]["enum"] == ["fr", "ar", "ary"]


def test_given_the_contract_then_the_job_exposes_signed_downloads_and_never_file_keys():
    props = SCHEMAS["ExportJob"]["properties"]
    assert {"id", "state", "format", "lang", "sha256", "row_count", "expires_at", "downloads"} <= set(props)
    assert "file_keys" not in props and "download_url" not in props
    assert props["downloads"]["additionalProperties"]["format"] == "uri"


def test_given_a_request_then_the_202_and_the_job_status_match_the_contract(client, token_for, world):
    w = world
    h = auth(token_for(w["owner"]))
    op = add_operation(w["farm_a"], w["owner"], w["a1"], type_="phyto")
    add_registry(w["farm_a"], op, w["a1"])
    created = client.post(f"/v1/farms/{w['farm_a']}/registry/exports", headers=h, json=EXPORT)
    assert created.status_code == 202 and set(created.json()) == {"id", "state", "row_count"}
    got = client.get(f"/v1/farms/{w['farm_a']}/registry/exports/{created.json()['id']}", headers=h).json()
    assert set(SCHEMAS["ExportJob"]["properties"]) >= set(got) and {"id", "state", "downloads"} <= set(got)


def test_given_a_finished_job_then_the_downloads_are_keyed_by_format(client, token_for, world):
    w = world
    job = add_job(w["farm_a"], w["owner"])
    got = client.get(f"/v1/farms/{w['farm_a']}/registry/exports/{job}", headers=auth(token_for(w["owner"]))).json()
    assert set(got["downloads"]) == {"pdf", "xlsx"} and all(u.startswith("http") for u in got["downloads"].values())
