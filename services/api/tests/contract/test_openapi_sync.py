"""T036 - dev token and sync upload conform to contracts/openapi.yaml (AC3.2)."""
import os
import uuid
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator

from tests.helpers import auth, op

SPEC = Path(os.environ.get("AYLAL_REPO_DIR", "/repo")) / "specs/001-foundations/contracts/openapi.yaml"


def _validate(instance: object, schema_name: str) -> None:
    spec = yaml.safe_load(SPEC.read_text(encoding="utf-8"))
    schema = {"$ref": f"#/components/schemas/{schema_name}", "components": spec["components"]}
    Draft202012Validator(schema).validate(instance)


def test_dev_token_response_matches_the_contract(client, clean_db) -> None:
    r = client.post("/v1/auth/dev-token", json={"user_id": str(uuid.uuid4())})
    assert r.status_code == 200
    assert {"token", "expires_at"} <= set(r.json())


def test_upload_response_matches_the_upload_result_schema(client, token_for, make_farm) -> None:
    user = uuid.uuid4()
    farm = make_farm({user: "owner"})
    batch = {"ops": [op(farm, uuid.uuid4(), kind="put", fields={"title": "a"})]}
    r = client.post("/v1/sync/upload", json=batch, headers=auth(token_for(user)))
    assert r.status_code == 200
    _validate(batch, "UploadBatch")
    _validate(r.json(), "UploadResult")
    assert [x["op_id"] for x in r.json()["results"]] == [o["op_id"] for o in batch["ops"]]


def test_upload_without_token_is_401(client, clean_db) -> None:
    assert client.post("/v1/sync/upload", json={"ops": []}).status_code == 401


def test_upload_malformed_batch_is_422(client, token_for) -> None:
    r = client.post("/v1/sync/upload", json={"nope": 1}, headers=auth(token_for(uuid.uuid4())))
    assert r.status_code == 422


@pytest.mark.parametrize("n,expected", [(501, 422)])
def test_upload_batch_over_500_ops_is_422(client, token_for, make_farm, n, expected) -> None:
    user = uuid.uuid4()
    farm = make_farm({user: "owner"})
    ops = [op(farm, uuid.uuid4(), kind="put", fields={"title": "x"}) for _ in range(n)]
    r = client.post("/v1/sync/upload", json={"ops": ops}, headers=auth(token_for(user)))
    assert r.status_code == expected
