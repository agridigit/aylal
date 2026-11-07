"""T033 - R1-A2, R1-A5: 30 days of offline entries replayed without loss; field-by-field conflicts keep both versions."""
import datetime as dt
import uuid

from tests.helpers import auth, sql
from tests.integration._f6 import TODAY, add_operation, sync_op, world  # noqa: F401


def upload(client, token_for, who, ops):
    return client.post("/v1/sync/upload", headers=auth(token_for(who)), json={"ops": ops})


def patch(farm, rid, fields, base_version):
    return {**sync_op("operations", farm, rid, fields, kind="patch"), "base_version": base_version}


def put(farm, rid, parcel, day, **extra):
    return sync_op("operations", farm, rid, {"type": "irrigation", "performed_on": day.isoformat(), "parcel_ids": [str(parcel)], **extra})


def test_given_thirty_days_of_offline_operations_when_replayed_then_none_is_lost_and_the_batch_limit_is_respected(client, token_for, world):
    w = world
    ops = [put(w["farm_a"], uuid.uuid4(), w["a1"], TODAY - dt.timedelta(days=d)) for d in range(30)]
    for chunk in (ops[:15], ops[15:]):
        r = upload(client, token_for, w["owner"], chunk)
        assert r.status_code == 200, r.text
        assert [x["status"] for x in r.json()["results"]] == ["applied"] * len(chunk)
    assert sql("SELECT count(*) FROM operations WHERE farm_id=$1", w["farm_a"])[0][0] == 30
    assert sql("SELECT count(*) FROM operation_parcels WHERE farm_id=$1", w["farm_a"])[0][0] == 30


def test_given_the_same_batch_replayed_after_a_network_cut_then_it_is_idempotent_by_op_id(client, token_for, world):
    w = world
    ops = [put(w["farm_a"], uuid.uuid4(), w["a1"], TODAY) for _ in range(3)]
    first = upload(client, token_for, w["owner"], ops).json()["results"]
    again = upload(client, token_for, w["owner"], ops).json()["results"]
    assert [r["status"] for r in first] == ["applied"] * 3 and [r["status"] for r in again] == ["duplicate"] * 3
    assert sql("SELECT count(*) FROM operations WHERE farm_id=$1", w["farm_a"])[0][0] == 3


def test_given_the_same_record_sent_with_new_op_ids_then_one_operation_exists(client, token_for, world):
    w = world
    rid = uuid.uuid4()
    upload(client, token_for, w["owner"], [put(w["farm_a"], rid, w["a1"], TODAY)])
    r = upload(client, token_for, w["owner"], [put(w["farm_a"], rid, w["a1"], TODAY)])
    assert r.status_code == 200
    assert sql("SELECT count(*) FROM operations WHERE id=$1", rid)[0][0] == 1


def test_given_a_batch_over_100_operations_then_413_and_nothing_is_written(client, token_for, world):
    w = world
    ops = [put(w["farm_a"], uuid.uuid4(), w["a1"], TODAY) for _ in range(101)]
    assert upload(client, token_for, w["owner"], ops).status_code == 413
    assert sql("SELECT count(*) FROM operations")[0][0] == 0


def test_given_an_offline_worker_operation_when_replayed_then_it_awaits_validation_and_the_worker_reads_it_back(client, token_for, world):
    w = world
    rid = uuid.uuid4()
    assert upload(client, token_for, w["worker"], [put(w["farm_a"], rid, w["a1"], TODAY)]).status_code == 200
    mine = client.get(f"/v1/farms/{w['farm_a']}/operations/{rid}", headers=auth(token_for(w["worker"])))
    assert mine.status_code == 200 and mine.json()["status"] == "pending_validation"


def test_given_two_devices_editing_different_fields_then_both_changes_are_kept(client, token_for, world):
    w = world
    oid = add_operation(w["farm_a"], w["owner"], w["a1"])
    a = sync_op("operations", w["farm_a"], oid, {"note": "from phone A"}, kind="patch")
    b = sync_op("operations", w["farm_a"], oid, {"operator_name": "Said"}, kind="patch")
    assert upload(client, token_for, w["owner"], [a]).status_code == 200
    assert upload(client, token_for, w["manager"], [b]).status_code == 200
    row = sql("SELECT note, operator_name FROM operations WHERE id=$1", oid)[0]
    assert (row["note"], row["operator_name"]) == ("from phone A", "Said")


def test_given_two_devices_editing_the_same_field_then_both_versions_are_in_the_corrections_history_and_flagged_as_a_conflict(client, token_for, world):
    w = world
    oid = add_operation(w["farm_a"], w["owner"], w["a1"])
    first = patch(w["farm_a"], oid, {"note": "version A"}, 1)
    stale = patch(w["farm_a"], oid, {"note": "version B"}, 1)
    assert upload(client, token_for, w["owner"], [first]).status_code == 200
    assert upload(client, token_for, w["manager"], [stale]).status_code == 200
    rows = sql("SELECT field, after::text, source FROM operation_corrections WHERE operation_id=$1 AND field='note' ORDER BY corrected_at, id", oid)
    assert len(rows) == 2
    assert {r["after"] for r in rows} == {'"version A"', '"version B"'}
    assert [r["source"] for r in rows].count("sync_conflict") >= 1
    history = client.get(f"/v1/farms/{w['farm_a']}/operations/{oid}/corrections", headers=auth(token_for(w["owner"]))).json()["items"]
    assert {h["after"] for h in history if h["field"] == "note"} == {"version A", "version B"}


def test_given_a_conflict_on_a_phyto_treatment_then_the_registry_keeps_a_reversal_for_each_replaced_version(client, token_for, world):
    w = world
    rid = uuid.uuid4()
    upload(client, token_for, w["owner"], [put(w["farm_a"], rid, w["a1"], TODAY, type="phyto", free_product_name="Maison", dose=1, dose_unit="L/ha")])
    base = sql("SELECT server_version FROM operations WHERE id=$1", rid)[0][0]
    for dose in (2, 3):
        upload(client, token_for, w["owner"], [patch(w["farm_a"], rid, {"dose": dose}, base)])
    kinds = [r[0] for r in sql("SELECT entry_kind FROM registry_entries WHERE operation_id=$1 ORDER BY recorded_at, id", rid)]
    assert kinds == ["application", "reversal", "application", "reversal", "application"]
    assert sql("SELECT count(*) FROM registry_current WHERE operation_id=$1", rid)[0][0] == 1


def test_given_a_worker_after_the_parcel_was_archived_when_replaying_an_old_offline_operation_then_it_is_refused_without_a_partial_write(client, token_for, world):
    w = world
    sql("UPDATE parcels SET archived_at=now() WHERE id=$1", w["a1"])
    rid = uuid.uuid4()
    r = upload(client, token_for, w["worker"], [put(w["farm_a"], rid, w["a1"], TODAY - dt.timedelta(days=10))])
    assert r.status_code == 404
    assert sql("SELECT count(*) FROM operations WHERE id=$1", rid)[0][0] == 0
