"""T019 - specs/003-fields-crops/contracts/openapi.yaml is valid YAML and in sync with the running API, both ways."""
import os
import re
from pathlib import Path

import yaml

REPO = Path(os.environ.get("AYLAL_REPO_DIR", "/repo"))
SPEC = REPO / "specs/003-fields-crops/contracts/openapi.yaml"
METHODS = {"get", "post", "patch", "put", "delete"}
F2_PREFIXES = ("/v1/crops", "/v1/farms/{farm_id}/fields", "/v1/farms/{farm_id}/crops")


def _spec() -> dict:
    return yaml.safe_load(SPEC.read_text(encoding="utf-8"))


def test_given_the_f2_contract_when_parsing_it_with_a_yaml_parser_then_it_is_valid_and_lists_the_routes():
    spec = _spec()
    assert spec["openapi"].startswith("3.") and len(spec["paths"]) >= 11


def test_given_the_f2_powersync_rules_contract_when_parsing_it_then_it_is_valid_yaml_with_buckets():
    rules = yaml.safe_load((REPO / "specs/003-fields-crops/contracts/powersync-sync-rules.yaml").read_text(encoding="utf-8"))
    assert {"farm_data", "farm_worker_parcels"} <= set(rules["bucket_definitions"])


def test_given_the_contract_when_comparing_with_the_running_api_then_every_documented_method_exists(client):
    live = client.get("/openapi.json").json()["paths"]
    for path, item in _spec()["paths"].items():
        assert path in live, f"documented but not served: {path}"
        assert {m for m in item if m in METHODS} <= set(live[path]), path


def test_given_the_running_api_when_listing_f2_routes_then_every_one_is_documented_in_the_contract(client):
    live = client.get("/openapi.json").json()["paths"]
    documented = _spec()["paths"]
    for path, item in live.items():
        if not path.startswith(F2_PREFIXES):
            continue
        assert path in documented, f"served but undocumented: {path}"
        assert {m for m in item if m in METHODS} <= set(documented[path]), (path, set(item) - set(documented[path]))


def test_given_the_contract_responses_when_reading_them_then_every_key_is_an_http_status_and_quoted():
    for path, item in _spec()["paths"].items():
        for method, op in item.items():
            if method in METHODS:
                assert all(re.fullmatch(r"\d{3}", str(k)) for k in op["responses"]), (path, method)
