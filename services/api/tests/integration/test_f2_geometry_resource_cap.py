"""T077 - an oversized ring is refused fast (422 / rejected op) on REST and sync, never a timeout (DoS)."""
import time
import uuid

import pytest

from tests.helpers import auth
from tests.integration._f2 import new_user

CYCLE = [[-7.6, 33.57], [-7.598, 33.57], [-7.598, 33.572], [-7.599, 33.573], [-7.6, 33.572]]


def giant(n=3000):
    return {"type": "Polygon", "coordinates": [[CYCLE[i % 5] for i in range(n)] + [CYCLE[0]]]}


@pytest.fixture
def owner_farm(make_farm):
    owner = new_user()
    return owner, make_farm({owner: "owner"})


def test_given_a_giant_ring_when_posting_a_field_then_422_is_returned_fast(client, token_for, owner_farm):
    owner, farm = owner_farm
    start = time.perf_counter()
    r = client.post(f"/v1/farms/{farm}/fields", headers=auth(token_for(owner)), json={"name": "Giant", "geometry": giant()})
    assert r.status_code == 422
    assert time.perf_counter() - start < 1.0


def test_given_a_giant_ring_when_uploading_a_sync_put_then_the_op_is_not_applied_fast(client, token_for, owner_farm):
    owner, farm = owner_farm
    op = {"op_id": str(uuid.uuid4()), "table": "parcels", "kind": "put", "record_id": str(uuid.uuid4()), "farm_id": str(farm),
          "base_version": 0, "fields": {"name": "Giant", "geometry": giant()}}
    start = time.perf_counter()
    r = client.post("/v1/sync/upload", headers=auth(token_for(owner)), json={"ops": [op]})
    assert time.perf_counter() - start < 1.0
    assert r.status_code in (200, 422)
    if r.status_code == 200:
        assert r.json()["results"][0]["status"] != "applied"
