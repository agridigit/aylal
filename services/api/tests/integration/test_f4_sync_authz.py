"""T019 - G1: the same access control on /v1/sync/upload for irrigation systems, events and analyses."""
import uuid

from tests.helpers import sql
from tests.integration._f4 import (  # noqa: F401
    TODAY4,
    seed_event,
    sync_event,
    sync_op,
    sync_post,
    world4,
)


def _count():
    return sql("SELECT count(*) FROM irrigation_events")[0][0]


def test_given_a_worker_when_uploading_an_event_on_an_assigned_parcel_then_it_is_written_with_the_server_author_and_operation(client, token_for, world4):
    from app.irrigation.ids import operation_id_for

    w, rid = world4, uuid.uuid4()
    r = sync_post(client, token_for(w["worker"]), [sync_event(w["farm_a"], w["a1"], rid)])
    assert r.status_code == 200 and r.json()["results"][0]["status"] == "applied", r.text
    row = sql("SELECT author_id, parcel_id, farm_id, operation_id, net_mm, volume_m3 FROM irrigation_events WHERE id=$1", rid)[0]
    assert (row["author_id"], row["parcel_id"], row["farm_id"]) == (w["worker"], w["a1"], w["farm_a"])
    assert row["operation_id"] == operation_id_for(w["farm_a"], rid) and row["volume_m3"] is not None  # derived by the server
    assert sql("SELECT count(*) FROM operations WHERE id=$1 AND type='irrigation'", row["operation_id"])[0][0] == 1


def test_given_a_batch_with_a_role_violation_then_403_for_the_whole_batch_and_nothing_is_written(client, token_for, world4):
    w = world4
    ok = sync_event(w["farm_a"], w["a1"])
    system = sync_op("irrigation_systems", w["farm_a"], uuid.uuid4(), {"parcel_id": str(w["a1"]), "kind": "drip", "sectors_count": 2, "pump_flow_m3h": 10})
    assert sync_post(client, token_for(w["worker"]), [sync_event(w["farm_a"], w["a1"])]).status_code == 200
    before, systems = _count(), sql("SELECT count(*) FROM irrigation_systems")[0][0]
    r = sync_post(client, token_for(w["worker"]), [ok, system])
    assert r.status_code == 403, r.text
    assert _count() == before and sql("SELECT count(*) FROM irrigation_systems")[0][0] == systems


def test_given_a_worker_when_uploading_a_water_analysis_then_403_and_nothing_is_written(client, token_for, world4):
    w = world4
    op = sync_op("water_analyses", w["farm_a"], uuid.uuid4(), {"parcel_id": str(w["a1"]), "ec_ds_m": 2.0, "analysed_on": "2026-06-01"})
    assert sync_post(client, token_for(w["worker"]), [sync_event(w["farm_a"], w["a1"])]).status_code == 200
    assert sync_post(client, token_for(w["worker"]), [op]).status_code == 403
    assert sql("SELECT count(*) FROM water_analyses")[0][0] == 0


def test_given_a_non_member_then_404_and_nothing_is_written(client, token_for, world4):
    w = world4
    assert sync_post(client, token_for(w["worker"]), [sync_event(w["farm_a"], w["a1"])]).status_code == 200
    before = _count()
    assert sync_post(client, token_for(w["outsider"]), [sync_event(w["farm_a"], w["a1"])]).status_code == 404
    assert sync_post(client, token_for(w["owner_b"]), [sync_event(w["farm_a"], w["a1"])]).status_code == 404
    assert _count() == before


def test_given_a_parcel_not_assigned_then_404_and_nothing_is_written(client, token_for, world4):
    w = world4
    assert sync_post(client, token_for(w["worker"]), [sync_event(w["farm_a"], w["a1"])]).status_code == 200
    before = _count()
    assert sync_post(client, token_for(w["worker"]), [sync_event(w["farm_a"], w["hidden"])]).status_code == 404
    assert _count() == before


def test_given_server_owned_fields_when_uploading_then_they_are_ignored_or_rejected_and_never_written(client, token_for, world4):
    w, rid = world4, uuid.uuid4()
    evil = dict(farm_id=str(w["farm_b"]), author_id=str(w["owner"]), operation_id=str(uuid.uuid4()), net_mm=999, volume_m3=999,
                parcel_archived_at="2026-01-01T00:00:00Z", server_version=77, status="cancelled")
    r = sync_post(client, token_for(w["worker"]), [sync_event(w["farm_a"], w["a1"], rid, **evil)])
    assert r.status_code == 200, r.text
    if r.json()["results"][0]["status"] == "applied":
        row = sql("SELECT farm_id, author_id, operation_id, net_mm, volume_m3, parcel_archived_at, server_version, status FROM irrigation_events WHERE id=$1", rid)[0]
        assert row["farm_id"] == w["farm_a"] and row["author_id"] == w["worker"]
        assert str(row["operation_id"]) != evil["operation_id"] and float(row["net_mm"] or 0) != 999 and float(row["volume_m3"] or 0) != 999
        assert row["parcel_archived_at"] is None and row["server_version"] != 77 and row["status"] == "done"
    else:
        assert sql("SELECT count(*) FROM irrigation_events WHERE id=$1", rid)[0][0] == 0


def test_given_the_same_op_sent_twice_then_it_is_applied_once_and_the_same_client_id_is_idempotent(client, token_for, world4):
    w, rid = world4, uuid.uuid4()
    op = sync_event(w["farm_a"], w["a1"], rid)
    first = sync_post(client, token_for(w["worker"]), [op])
    assert first.json()["results"][0]["status"] == "applied", first.text
    assert sync_post(client, token_for(w["worker"]), [op]).json()["results"][0]["status"] == "duplicate"
    again = sync_post(client, token_for(w["worker"]), [sync_event(w["farm_a"], w["a1"], rid)])  # same id, new op id
    assert again.status_code == 200
    assert sql("SELECT count(*) FROM irrigation_events WHERE id=$1", rid)[0][0] == 1
    assert sql("SELECT count(*) FROM applied_ops WHERE op_id=$1", uuid.UUID(op["op_id"]))[0][0] == 1


def test_given_a_client_id_colliding_with_an_event_of_another_farm_then_404_identical_and_the_other_farm_is_untouched(client, token_for, world4):
    w = world4
    theirs = seed_event(w["farm_b"], w["b1"], w["owner_b"])
    r = sync_post(client, token_for(w["worker"]), [sync_event(w["farm_a"], w["a1"], theirs)])
    ghost = sync_post(client, token_for(w["worker"]), [sync_event(w["farm_a"], w["a1"], uuid.uuid4(), parcel_id=str(uuid.uuid4()))])
    assert r.status_code == 404 and r.json() == ghost.json()
    assert sql("SELECT farm_id, status FROM irrigation_events WHERE id=$1", theirs)[0][:] == (w["farm_b"], "done")


def test_given_a_cancel_patch_by_the_author_then_the_event_is_cancelled_never_deleted(client, token_for, world4):
    w = world4
    mine, theirs = seed_event(w["farm_a"], w["a1"], w["worker"]), seed_event(w["farm_a"], w["a1"], w["owner"])
    ok = sync_op("irrigation_events", w["farm_a"], mine, {"status": "cancelled"}, kind="patch")
    assert sync_post(client, token_for(w["worker"]), [ok]).status_code == 200
    assert sql("SELECT status FROM irrigation_events WHERE id=$1", mine)[0][0] == "cancelled"
    bad = sync_op("irrigation_events", w["farm_a"], theirs, {"status": "cancelled"}, kind="patch")
    assert sync_post(client, token_for(w["worker"]), [bad]).status_code == 403
    assert sql("SELECT status FROM irrigation_events WHERE id=$1", theirs)[0][0] == "done"
    delete = sync_op("irrigation_events", w["farm_a"], theirs, {}, kind="delete")
    assert sync_post(client, token_for(w["owner"]), [delete]).status_code in (400, 403, 422)
    assert sql("SELECT count(*) FROM irrigation_events WHERE id=$1", theirs)[0][0] == 1
    assert TODAY4
