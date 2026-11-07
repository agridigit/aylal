"""T022 - specs/005-operations-journal/contracts/openapi.yaml is in sync with the running API, both ways."""
import os
from pathlib import Path

import yaml

REPO = Path(os.environ.get("AYLAL_REPO_DIR", "/repo"))
SPEC = REPO / "specs/005-operations-journal/contracts/openapi.yaml"
METHODS = {"get", "post", "patch", "put", "delete"}
F6_PREFIXES = ("/v1/farms/{farm_id}/operations", "/v1/farms/{farm_id}/registry", "/v1/farms/{farm_id}/phyto-products",
               "/v1/phyto-products", "/v1/farms/{farm_id}/fields/{field_id}/earliest-harvest")


def _spec() -> dict:
    return yaml.safe_load(SPEC.read_text(encoding="utf-8"))


def test_given_the_contract_when_comparing_with_the_running_api_then_every_documented_method_exists(client):
    live = client.get("/openapi.json").json()["paths"]
    for path, item in _spec()["paths"].items():
        if path == "/v1/sync/upload":
            continue
        assert path in live, f"documented but not served: {path}"
        assert {m for m in item if m in METHODS} <= set(live[path]), path


def test_given_the_running_api_when_listing_f6_routes_then_every_one_is_documented(client):
    live = client.get("/openapi.json").json()["paths"]
    documented = _spec()["paths"]
    served = [p for p in live if p.startswith(F6_PREFIXES)]
    assert served, "no F6 route is served"
    for path in served:
        assert path in documented, f"served but undocumented: {path}"
        assert {m for m in live[path] if m in METHODS} <= set(documented[path]), path


def test_given_the_input_schema_then_it_carries_no_storage_key_field_and_server_object_key_is_read_only(client):
    schemas = _spec()["components"]["schemas"]
    props = schemas["OperationInput"]["properties"]
    assert "label_photo_key" not in props and "file_keys" not in props and "label_photo_id" in props
    assert schemas["ServerObjectKey"]["readOnly"] is True
    live = client.get("/openapi.json").json()["components"]["schemas"]
    assert "OperationInput" in live
    assert "label_photo_key" not in live["OperationInput"]["properties"]
