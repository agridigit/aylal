"""T017 - G1: the same access control on /v1/sync/upload for zone observations."""
import uuid

from tests.helpers import sql
from tests.integration._f3 import call, seed_zone, sync_obs, sync_post, world3  # noqa: F401


def _count():
    return sql("SELECT count(*) FROM zone_observations")[0][0]


def test_given_a_worker_when_uploading_an_observation_on_an_assigned_zone_then_it_is_written_with_the_server_author(client, token_for, world3):
    w = world3
    z, rid = seed_zone(w["farm_a"], w["a1"]), uuid.uuid4()
    r = sync_post(client, token_for(w["worker"]), [sync_obs(w["farm_a"], z, rid=rid)])
    assert r.status_code == 200 and r.json()["results"][0]["status"] == "applied", r.text
    row = sql("SELECT author_id, parcel_id, farm_id FROM zone_observations WHERE id=$1", rid)[0]
    assert (row["author_id"], row["parcel_id"], row["farm_id"]) == (w["worker"], w["a1"], w["farm_a"])


def test_given_a_batch_with_a_role_violation_then_403_for_the_whole_batch_and_nothing_is_written(client, token_for, world3):
    w = world3
    z = seed_zone(w["farm_a"], w["a1"])
    ok = sync_obs(w["farm_a"], z)
    dismiss = {"op_id": str(uuid.uuid4()), "table": "attention_zones", "kind": "patch", "record_id": str(z), "farm_id": str(w["farm_a"]),
               "base_version": 0, "fields": {"status": "dismissed"}}
    assert sync_post(client, token_for(w["worker"]), [sync_obs(w["farm_a"], z)]).status_code == 200
    before = _count()
    r = sync_post(client, token_for(w["worker"]), [ok, dismiss])
    assert r.status_code == 403, r.text
    assert _count() == before and sql("SELECT status FROM attention_zones WHERE id=$1", z)[0][0] == "open"


def test_given_a_non_member_then_404_and_nothing_is_written(client, token_for, world3):
    w = world3
    z = seed_zone(w["farm_a"], w["a1"])
    assert sync_post(client, token_for(w["worker"]), [sync_obs(w["farm_a"], z)]).status_code == 200
    before = _count()
    assert sync_post(client, token_for(w["outsider"]), [sync_obs(w["farm_a"], z)]).status_code == 404
    assert sync_post(client, token_for(w["owner_b"]), [sync_obs(w["farm_a"], z)]).status_code == 404
    assert _count() == before


def test_given_a_zone_of_a_parcel_not_assigned_then_404_and_nothing_is_written(client, token_for, world3):
    w = world3
    z = seed_zone(w["farm_a"], w["hidden"])
    assert sync_post(client, token_for(w["worker"]), [sync_obs(w["farm_a"], seed_zone(w["farm_a"], w["a1"]))]).status_code == 200
    before = _count()
    assert sync_post(client, token_for(w["worker"]), [sync_obs(w["farm_a"], z)]).status_code == 404
    assert _count() == before


def test_given_server_owned_fields_when_uploading_then_they_are_ignored_or_rejected_and_never_written(client, token_for, world3):
    w = world3
    z, rid = seed_zone(w["farm_a"], w["a1"]), uuid.uuid4()
    r = sync_post(client, token_for(w["worker"]), [sync_obs(w["farm_a"], z, rid=rid, author_id=str(w["owner"]), photo_key="farms/x/zone-photos/y",
                                                            status="resolved", parcel_archived_at="2026-01-01T00:00:00Z", parcel_id=str(w["hidden"]))])
    assert r.status_code == 200, r.text
    if r.json()["results"][0]["status"] == "applied":
        row = sql("SELECT author_id, photo_key, parcel_id, parcel_archived_at FROM zone_observations WHERE id=$1", rid)[0]
        assert (row["author_id"], row["photo_key"], row["parcel_id"], row["parcel_archived_at"]) == (w["worker"], None, w["a1"], None)
    else:
        assert sql("SELECT count(*) FROM zone_observations WHERE id=$1", rid)[0][0] == 0
    assert sql("SELECT status FROM attention_zones WHERE id=$1", z)[0][0] == "open"


def test_given_the_same_op_sent_twice_then_it_is_applied_once(client, token_for, world3):
    w = world3
    z = seed_zone(w["farm_a"], w["a1"])
    op = sync_obs(w["farm_a"], z)
    first = sync_post(client, token_for(w["worker"]), [op])
    assert first.json()["results"][0]["status"] == "applied", first.text
    again = sync_post(client, token_for(w["worker"]), [op])
    assert again.json()["results"][0]["status"] == "duplicate"
    assert sql("SELECT count(*) FROM zone_observations WHERE zone_id=$1", z)[0][0] == 1
    assert sql("SELECT count(*) FROM applied_ops WHERE op_id=$1", uuid.UUID(op["op_id"]))[0][0] == 1
