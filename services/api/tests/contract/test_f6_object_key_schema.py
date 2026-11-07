"""T022a (contract) - no storage key is accepted from clients: OpenAPI input schemas and PowerSync rules."""
import os
import re
from pathlib import Path

import yaml

REPO = Path(os.environ.get("AYLAL_REPO_DIR", "/repo"))
PATTERN = r"^farms/[0-9a-f-]{36}/(labels|exports)/[0-9a-f-]{36}(/[A-Za-z0-9._-]+)?$"


def test_given_the_contract_then_server_object_key_is_read_only_with_the_expected_pattern():
    schemas = yaml.safe_load((REPO / "specs/005-operations-journal/contracts/openapi.yaml").read_text())["components"]["schemas"]
    assert schemas["ServerObjectKey"]["readOnly"] is True and schemas["ServerObjectKey"]["pattern"] == PATTERN


def test_given_the_live_openapi_then_input_schemas_have_no_storage_key_property_and_forbid_extra_fields(client):
    live = client.get("/openapi.json").json()["components"]["schemas"]
    assert "OperationInput" in live, "F6 input schema not served"
    for name, schema in live.items():
        if name.endswith(("Input", "Request", "Create")) and any(k in name for k in ("Operation", "Export", "Registry")):
            props = schema.get("properties", {})
            assert not ({"label_photo_key", "file_keys", "object_key"} & set(props)), name
            assert schema.get("additionalProperties") is False, f"{name} must be strict"


def test_given_the_sync_rules_then_storage_keys_are_never_replicated():
    text = (REPO / "infra/powersync/sync-rules.yaml").read_text()
    assert "FROM operations" in text, "F6 rules missing"
    body = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
    for key in ("label_photo_key", "file_keys", "object_key"):
        assert key not in body
    assert not re.search(r"SELECT \* FROM (operations|export_jobs|label_uploads)\b", body)
