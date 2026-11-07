"""E2E (pytest + httpx on the Docker stack, through the TLS proxy): offline queue -> sync -> replay."""
import uuid

import httpx

from tests.helpers import sql

BASE = "https://proxy/v1"


def test_given_a_queued_offline_creation_when_the_network_returns_then_it_is_stored_once() -> None:
    user, farm_id, rid = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    sql("INSERT INTO farms (id, name) VALUES ($1, 'e2e farm')", farm_id)
    sql("INSERT INTO farm_members (farm_id, user_id, role) VALUES ($1, $2, 'manager')", farm_id, user)
    with httpx.Client(base_url=BASE, verify=False, timeout=30) as c:
        r = c.post("/auth/dev-token", json={"user_id": str(user)})
        assert r.status_code == 200
        h = {"Authorization": f"Bearer {r.json()['token']}"}
        batch = {
            "ops": [
                {
                    "op_id": str(uuid.uuid4()),
                    "table": "trial_records",
                    "kind": "put",
                    "record_id": str(rid),
                    "farm_id": str(farm_id),
                    "base_version": 0,
                    "fields": {"title": "offline entry", "quantity": 3},
                }
            ]
        }
        first = c.post("/sync/upload", json=batch, headers=h).json()["results"][0]
        again = c.post("/sync/upload", json=batch, headers=h).json()["results"][0]
    assert first["status"] == "applied"
    assert again["status"] == "duplicate"
    assert len(sql("SELECT 1 FROM trial_records WHERE id = $1", rid)) == 1
