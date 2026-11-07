"""T047 - a farm created offline with a client UUID is synchronised later (R4-A3)."""
import uuid

from tests.helpers import auth
from tests.integration._auth_flow import _test_otp, login  # noqa: F401

CASA = {"lat": 33.5731, "lon": -7.5898}


def _create_op(farm_id, **fields):
    return {
        "op_id": str(uuid.uuid4()), "table": "farms", "kind": "put", "record_id": str(farm_id),
        "farm_id": str(farm_id), "base_version": 0, "fields": {"name": "Ferme hors ligne", "location": CASA, **fields},
    }


def test_given_a_farm_created_offline_when_syncing_then_it_exists_server_side_with_the_client_uuid(client):
    s = login(client)
    fid = uuid.uuid4()
    r = client.post("/v1/sync/upload", json={"ops": [_create_op(fid)]}, headers=auth(s["access_token"]))
    assert r.status_code == 200 and r.json()["results"][0]["status"] == "applied"
    farms = client.get("/v1/farms", headers=auth(s["access_token"])).json()
    assert [(f["id"], f["role"], f["owner_id"]) for f in farms] == [(str(fid), "owner", s["user"]["id"])]
    assert farms[0]["commune_id"] is not None


def test_given_the_same_creation_replayed_when_syncing_then_no_duplicate_farm_exists(client):
    s = login(client)
    op = _create_op(uuid.uuid4())
    for _ in range(2):
        assert client.post("/v1/sync/upload", json={"ops": [op]}, headers=auth(s["access_token"])).status_code == 200
    assert len(client.get("/v1/farms", headers=auth(s["access_token"])).json()) == 1


def test_given_an_offline_farm_without_location_when_syncing_then_it_is_rejected_not_created(client):
    s = login(client)
    op = _create_op(uuid.uuid4())
    del op["fields"]["location"]
    r = client.post("/v1/sync/upload", json={"ops": [op]}, headers=auth(s["access_token"]))
    assert r.json()["results"][0]["status"] == "rejected"
    assert client.get("/v1/farms", headers=auth(s["access_token"])).json() == []


def test_given_a_pending_farm_endpoint_when_reading_sync_status_then_the_server_exposes_no_pending_flag(client):
    """The pending indicator is local (queue), the server only ever returns synchronised farms."""
    s = login(client)
    client.post("/v1/farms", json={"name": "F", "location": CASA}, headers=auth(s["access_token"]))
    assert all("pending" not in f for f in client.get("/v1/farms", headers=auth(s["access_token"])).json())
