"""T041 - the server rejects what the shared T008 vectors declare invalid (AC3.5)."""
import json
import os
import uuid
from pathlib import Path

import pytest

from tests.helpers import op, record_row

VECTORS = json.loads(
    (Path(os.environ.get("AYLAL_DOMAIN_DIR", "/packages/domain")) / "vectors/trial_record.json").read_text()
)
CREATE = [v for v in VECTORS if v["rule"] == "trial_record.create"]


@pytest.mark.parametrize("vector", CREATE, ids=lambda v: f"{v['expect']['valid']}: {v['name']}")
def test_given_a_shared_vector_when_uploaded_as_a_put_then_the_server_verdict_matches(
    vector, client, token_for, make_farm, upload
) -> None:
    user, rid = uuid.uuid4(), uuid.uuid4()
    farm = make_farm({user: "manager"})
    res = upload(token_for(user), [op(farm, rid, kind="put", fields=vector["input"])])["results"][0]
    if vector["expect"]["valid"]:
        assert res["status"] == "applied"
        assert record_row(rid) is not None
    else:
        assert res["status"] == "rejected"
        assert res["error"]["code"] == "validation"
        assert res["error"]["field"] in {e["field"] for e in vector["expect"]["errors"]}
        assert record_row(rid) is None
