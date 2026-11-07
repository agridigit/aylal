"""T012 - G1: same access control on /v1/sync/upload for F6 tables."""
import uuid

from tests.helpers import auth, sql
from tests.integration._f6 import TODAY, add_operation, sync_op, world  # noqa: F401


def put(farm, rid, parcels, **extra):
    fields = {"type": "irrigation", "performed_on": TODAY.isoformat(), "parcel_ids": [str(p) for p in parcels], **extra}
    return sync_op("operations", farm, rid, fields)


def post(client, token_for, who, ops):
    return client.post("/v1/sync/upload", json={"ops": ops}, headers=auth(token_for(who)))


def count():
    return sql("SELECT count(*) FROM operations")[0][0]


def test_given_an_owner_when_uploading_an_operation_then_it_is_written(client, token_for, world):
    w = world
    rid = uuid.uuid4()
    r = post(client, token_for, w["owner"], [put(w["farm_a"], rid, [w["a1"]])])
    assert r.status_code == 200, r.text
    assert sql("SELECT status FROM operations WHERE id=$1", rid)[0][0] == "validated"


def test_given_a_worker_batch_with_one_violating_operation_then_403_for_the_whole_batch_and_nothing_is_written(client, token_for, world):
    w = world
    ok = put(w["farm_a"], uuid.uuid4(), [w["a1"]])
    bad = sync_op("operations", w["farm_a"], add_operation(w["farm_a"], w["manager"], w["a1"], status="pending_validation"),
                  {"status": "validated"}, kind="patch")
    before = count()
    r = post(client, token_for, w["worker"], [ok, bad])
    assert r.status_code == 403, r.text
    assert count() == before


def test_given_a_non_member_when_uploading_an_operation_then_404_and_nothing_is_written(client, token_for, world):
    w = world
    before = count()
    assert post(client, token_for, w["outsider"], [put(w["farm_a"], uuid.uuid4(), [w["a1"]])]).status_code == 404
    assert count() == before


def test_given_server_owned_fields_when_uploading_then_they_are_ignored(client, token_for, world):
    w = world
    rid = uuid.uuid4()
    r = post(client, token_for, w["worker"], [put(
        w["farm_a"], rid, [w["a1"]], status="validated", author_id=str(w["owner"]), warnings=[{"code": "x"}],
        validated_by=str(w["owner"]), registry_entry_id=str(uuid.uuid4()), parcel_archived_at="2026-01-01T00:00:00Z")])
    assert r.status_code == 200, r.text
    row = sql("SELECT status, author_id, validated_by FROM operations WHERE id=$1", rid)[0]
    assert row["status"] == "pending_validation" and row["author_id"] == w["worker"]
    assert row["validated_by"] is None
    assert sql("SELECT parcel_archived_at FROM operation_parcels WHERE operation_id=$1", rid)[0][0] is None


def test_given_an_operation_of_another_farm_when_patching_it_through_my_farm_then_404_and_it_is_unchanged(client, token_for, world):
    w = world
    theirs = add_operation(w["farm_b"], w["owner_b"], w["b1"])
    r = post(client, token_for, w["owner"], [sync_op("operations", w["farm_a"], theirs, {"note": "hacked"}, kind="patch")])
    assert r.status_code == 404, r.text
    assert sql("SELECT farm_id FROM operations WHERE id=$1", theirs)[0][0] == w["farm_b"]


def test_given_a_parcel_created_earlier_in_the_same_batch_then_the_operation_uses_it(client, token_for, world):
    w = world
    pid, rid = uuid.uuid4(), uuid.uuid4()
    from tests.integration._f2 import square

    parcel = sync_op("parcels", w["farm_a"], pid, {"name": "Fresh", "geometry": square(-7.9)})
    r = post(client, token_for, w["owner"], [parcel, put(w["farm_a"], rid, [pid])])
    assert r.status_code == 200, r.text
    assert sql("SELECT count(*) FROM operation_parcels WHERE operation_id=$1 AND parcel_id=$2", rid, pid)[0][0] == 1
