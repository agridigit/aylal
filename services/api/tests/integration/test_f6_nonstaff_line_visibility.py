"""T031b - hardening: a non-staff member cannot act (REST or sync) on an operation unless ALL its lines are visible to them."""
import uuid

from tests.helpers import auth, sql
from tests.integration._f6 import TODAY, add_operation, sync_op, world  # noqa: F401


def _two_line_operation(w, *, second="a2", archived=False, status="planned", type_="phyto"):
    """Authored by the worker: line 1 on the assigned parcel a1, line 2 on a parcel the worker does not see."""
    oid = add_operation(w["farm_a"], w["worker"], w["a1"], status=status, type_=type_)
    sql("INSERT INTO operation_parcels (id, farm_id, operation_id, parcel_id, author_id, type, performed_on, status, parcel_archived_at) "
        "VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)", uuid.uuid4(), w["farm_a"], oid, w[second], w["worker"], type_, TODAY, status,
        __import__("datetime").datetime.now(__import__("datetime").UTC) if archived else None)
    if archived:
        sql("UPDATE parcels SET archived_at=now() WHERE id=$1", w[second])
    return oid


def _unchanged(oid, status="planned"):
    assert sql("SELECT status FROM operations WHERE id=$1", oid)[0][0] == status
    assert sql("SELECT count(*) FROM registry_entries WHERE operation_id=$1", oid)[0][0] == 0


def test_given_a_worker_operation_with_an_unassigned_line_when_marking_done_then_404_and_nothing_is_written(client, token_for, world):
    w = world
    oid = _two_line_operation(w)
    r = client.post(f"/v1/farms/{w['farm_a']}/operations/{oid}/done", headers=auth(token_for(w["worker"])))
    assert r.status_code == 404, r.text
    _unchanged(oid)


def test_given_a_worker_operation_with_an_unassigned_line_when_cancelling_then_404_and_nothing_is_written(client, token_for, world):
    w = world
    oid = _two_line_operation(w)
    r = client.post(f"/v1/farms/{w['farm_a']}/operations/{oid}/cancel", headers=auth(token_for(w["worker"])))
    assert r.status_code == 404, r.text
    _unchanged(oid)


def test_given_a_worker_operation_with_an_archived_line_when_marking_done_then_404_and_nothing_is_written(client, token_for, world):
    w = world
    sql("INSERT INTO worker_parcels (farm_id, user_id, parcel_id) VALUES ($1,$2,$3)", w["farm_a"], w["worker"], w["a2"])
    oid = _two_line_operation(w, archived=True)
    r = client.post(f"/v1/farms/{w['farm_a']}/operations/{oid}/done", headers=auth(token_for(w["worker"])))
    assert r.status_code == 404, r.text
    _unchanged(oid)


def test_given_a_worker_operation_whose_lines_are_all_visible_when_marking_done_then_it_succeeds(client, token_for, world):
    w = world
    sql("INSERT INTO worker_parcels (farm_id, user_id, parcel_id) VALUES ($1,$2,$3)", w["farm_a"], w["worker"], w["a2"])
    oid = _two_line_operation(w)
    r = client.post(f"/v1/farms/{w['farm_a']}/operations/{oid}/done", headers=auth(token_for(w["worker"])))
    assert r.status_code == 200, r.text
    assert sql("SELECT status FROM operations WHERE id=$1", oid)[0][0] != "planned"


def test_given_staff_when_acting_on_a_multi_line_operation_then_it_still_works(client, token_for, world):
    w = world
    oid = _two_line_operation(w)
    r = client.post(f"/v1/farms/{w['farm_a']}/operations/{oid}/cancel", headers=auth(token_for(w["manager"])))
    assert r.status_code == 200, r.text


def _replay(w, oid):
    return sync_op("operations", w["farm_a"], oid,
                   {"type": "phyto", "performed_on": TODAY.isoformat(), "parcel_ids": [str(w["a1"])], "note": "tampered"})


def test_given_a_worker_replaying_over_sync_an_operation_with_an_unassigned_line_then_404_and_nothing_is_written(client, token_for, world):
    w = world
    oid = _two_line_operation(w)
    r = client.post("/v1/sync/upload", headers=auth(token_for(w["worker"])), json={"ops": [_replay(w, oid)]})
    assert r.status_code == 404, r.text
    assert sql("SELECT note FROM operations WHERE id=$1", oid)[0][0] is None
    assert sql("SELECT count(*) FROM operation_corrections WHERE operation_id=$1", oid)[0][0] == 0
    _unchanged(oid)


def test_given_a_worker_batch_with_one_invisible_operation_then_the_whole_batch_is_refused_and_nothing_is_written(client, token_for, world):
    w = world
    bad = _two_line_operation(w)
    ok = sync_op("operations", w["farm_a"], uuid.uuid4(),
                 {"type": "irrigation", "performed_on": TODAY.isoformat(), "parcel_ids": [str(w["a1"])]})
    before = sql("SELECT count(*) FROM operations")[0][0]
    r = client.post("/v1/sync/upload", headers=auth(token_for(w["worker"])), json={"ops": [ok, _replay(w, bad)]})
    assert r.status_code == 404, r.text
    assert sql("SELECT count(*) FROM operations")[0][0] == before
