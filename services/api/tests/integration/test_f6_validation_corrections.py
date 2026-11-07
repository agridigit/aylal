"""T075 - R7-A1 to R7-A4: a worker's operation is pending validation with the worker as operator; owner/manager validate it;
a correction is a compensating write (reversal + application) with its history; the registry is never updated in place."""
import datetime as dt
import uuid

import pytest

from tests.helpers import auth, sql
from tests.integration._f6 import add_operation, op_body, sync_op, world  # noqa: F401
from tests.integration._f2 import assign, new_user

TODAY = dt.date.today()


def treat(client, token_for, who, farm, parcel, **kw):
    body = op_body([parcel], type="phyto", free_product_name="Maison", dose=2, dose_unit="L/ha", **kw)
    r = client.post(f"/v1/farms/{farm}/operations", headers=auth(token_for(who)), json=body)
    assert r.status_code == 201, r.text
    return uuid.UUID(r.json()["id"]), r.json()


def registry(oid):
    return sql("SELECT id, entry_kind, supersedes_id, dose, operator_user_id, operator_name, recorded_by, xmin::text AS xmin "
               "FROM registry_entries WHERE operation_id=$1 ORDER BY recorded_at, id", oid)


def test_given_a_worker_when_recording_a_treatment_then_it_is_pending_validation_with_the_worker_as_operator(client, token_for, world):
    w = world
    sql("UPDATE users SET display_name='Karim' WHERE id=$1", w["worker"])
    oid, created = treat(client, token_for, w["worker"], w["farm_a"], w["a1"])
    assert created["status"] == "pending_validation"
    rows = registry(oid)
    assert [r["entry_kind"] for r in rows] == ["application"]
    assert rows[0]["operator_user_id"] == w["worker"] and rows[0]["operator_name"] == "Karim"
    assert sql("SELECT author_id, status FROM operations WHERE id=$1", oid)[0]["author_id"] == w["worker"]
    detail = client.get(f"/v1/farms/{w['farm_a']}/operations/{oid}", headers=auth(token_for(w["manager"]))).json()
    assert detail["operator_user_id"] == str(w["worker"]) and detail["status"] == "pending_validation"


def test_given_pending_operations_when_a_manager_lists_the_queue_then_the_worker_operations_to_validate_appear(client, token_for, world):
    w = world
    oid, _ = treat(client, token_for, w["worker"], w["farm_a"], w["a1"])
    mine, _ = treat(client, token_for, w["owner"], w["farm_a"], w["a1"])
    queue = client.get(f"/v1/farms/{w['farm_a']}/operations", headers=auth(token_for(w["manager"])), params={"status": "pending_validation"}).json()["items"]
    assert [i["id"] for i in queue] == [str(oid)] and mine not in [uuid.UUID(i["id"]) for i in queue]


@pytest.mark.parametrize("approver", ["owner", "manager"])
def test_given_a_pending_operation_when_staff_validates_then_it_is_validated_and_the_registry_row_is_untouched(client, token_for, world, approver):
    w = world
    oid, _ = treat(client, token_for, w["worker"], w["farm_a"], w["a1"])
    before = registry(oid)
    r = client.post(f"/v1/farms/{w['farm_a']}/operations/{oid}/validate", headers=auth(token_for(w[approver])))
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "validated" and r.json()["validated_by"] == str(w[approver]) and r.json()["validated_at"]
    assert [dict(x) for x in registry(oid)] == [dict(x) for x in before]  # same rows, same xmin: no UPDATE, no new row
    assert sql("SELECT status FROM operation_parcels WHERE operation_id=$1", oid)[0][0] == "validated"
    queue = client.get(f"/v1/farms/{w['farm_a']}/operations", headers=auth(token_for(w[approver])), params={"status": "pending_validation"}).json()["items"]
    assert queue == []


def test_given_a_worker_when_validating_or_correcting_or_reading_corrections_then_403_and_nothing_changes(client, token_for, world):
    w = world
    oid, _ = treat(client, token_for, w["worker"], w["farm_a"], w["a1"])
    before = registry(oid)
    h, f = auth(token_for(w["worker"])), f"/v1/farms/{w['farm_a']}/operations/{oid}"
    assert client.post(f"{f}/validate", headers=h).status_code == 403
    assert client.patch(f, headers=h, json={"dose": 9}).status_code == 403
    assert client.get(f"{f}/corrections", headers=h).status_code == 403
    assert sql("SELECT status FROM operations WHERE id=$1", oid)[0][0] == "pending_validation"
    assert [dict(x) for x in registry(oid)] == [dict(x) for x in before]
    assert sql("SELECT count(*) FROM operation_corrections WHERE operation_id=$1", oid)[0][0] == 0


@pytest.mark.parametrize("status", ["validated", "cancelled", "planned"])
def test_given_an_operation_not_pending_when_validating_then_409_and_the_status_is_unchanged(client, token_for, world, status):
    w = world
    day = TODAY + dt.timedelta(days=3) if status == "planned" else TODAY
    oid = add_operation(w["farm_a"], w["worker"], w["a1"], status=status, performed_on=day)
    r = client.post(f"/v1/farms/{w['farm_a']}/operations/{oid}/validate", headers=auth(token_for(w["manager"])))
    assert r.status_code == 409 and r.json()["detail"]["code"] == "invalid_transition"
    assert sql("SELECT status FROM operations WHERE id=$1", oid)[0][0] == status


def test_given_another_farm_when_validating_correcting_or_reading_corrections_then_404_identical_to_unknown(client, token_for, world):
    w = world
    oid, _ = treat(client, token_for, w["worker"], w["farm_a"], w["a1"])
    h = auth(token_for(w["owner_b"]))
    ghost = uuid.uuid4()
    for who_farm in (w["farm_a"], w["farm_b"]):
        for method, suffix, body in (("POST", "/validate", None), ("PATCH", "", {"dose": 3}), ("GET", "/corrections", None)):
            got = client.request(method, f"/v1/farms/{who_farm}/operations/{oid}{suffix}", headers=h, json=body)
            unknown = client.request(method, f"/v1/farms/{who_farm}/operations/{ghost}{suffix}", headers=h, json=body)
            assert got.status_code == 404 and got.json() == unknown.json(), (who_farm, method, suffix)
    assert sql("SELECT status FROM operations WHERE id=$1", oid)[0][0] == "pending_validation"


def test_given_a_validated_operation_when_a_manager_corrects_it_then_a_reversal_and_a_new_application_are_added_and_the_original_is_never_updated(client, token_for, world):
    w = world
    oid, _ = treat(client, token_for, w["worker"], w["farm_a"], w["a1"])
    client.post(f"/v1/farms/{w['farm_a']}/operations/{oid}/validate", headers=auth(token_for(w["owner"])))
    original = registry(oid)[0]
    r = client.patch(f"/v1/farms/{w['farm_a']}/operations/{oid}", headers=auth(token_for(w["manager"])), json={"dose": 3})
    assert r.status_code == 200, r.text
    rows = registry(oid)
    assert [x["entry_kind"] for x in rows] == ["application", "reversal", "application"]
    assert dict(rows[0]) == dict(original)                               # not even re-written: same xmin
    assert rows[1]["supersedes_id"] == original["id"] and rows[2]["supersedes_id"] is None
    assert float(rows[2]["dose"]) == 3 and float(rows[0]["dose"]) == 2
    assert rows[2]["operator_user_id"] == w["worker"]                    # the worker stays the operator of the work done
    assert rows[1]["recorded_by"] == w["manager"] and rows[2]["recorded_by"] == w["manager"]
    assert [float(x[0]) for x in sql("SELECT dose FROM registry_current WHERE operation_id=$1", oid)] == [3.0]
    assert sql("SELECT status FROM operations WHERE id=$1", oid)[0][0] == "validated"


def test_given_corrections_when_reading_the_history_then_who_when_before_and_after_are_listed_in_order(client, token_for, world):
    w = world
    oid, _ = treat(client, token_for, w["worker"], w["farm_a"], w["a1"])
    client.post(f"/v1/farms/{w['farm_a']}/operations/{oid}/validate", headers=auth(token_for(w["owner"])))
    f = f"/v1/farms/{w['farm_a']}/operations/{oid}"
    assert client.patch(f, headers=auth(token_for(w["manager"])), json={"dose": 3, "note": "after the rain"}).status_code == 200
    assert client.patch(f, headers=auth(token_for(w["owner"])), json={"dose": 4}).status_code == 200
    items = client.get(f"{f}/corrections", headers=auth(token_for(w["manager"]))).json()["items"]
    by = [(i["field"], i["before"], i["after"], i["author_id"]) for i in items]
    assert ("dose", 2, 3, str(w["manager"])) in by and ("note", None, "after the rain", str(w["manager"])) in by
    assert by[-1] == ("dose", 3, 4, str(w["owner"]))
    assert all(i["corrected_at"] and i["source"] == "manual" and uuid.UUID(i["id"]) for i in items)
    assert [i["corrected_at"] for i in items] == sorted(i["corrected_at"] for i in items)
    assert sql("SELECT count(*) FROM registry_entries WHERE operation_id=$1 AND entry_kind='reversal'", oid)[0][0] == 2


def test_given_a_correction_with_no_change_when_patching_then_no_history_and_no_registry_row_is_added(client, token_for, world):
    w = world
    oid, _ = treat(client, token_for, w["owner"], w["farm_a"], w["a1"])
    rows = len(registry(oid))
    assert client.patch(f"/v1/farms/{w['farm_a']}/operations/{oid}", headers=auth(token_for(w["owner"])), json={"dose": 2}).status_code == 200
    assert len(registry(oid)) == rows and sql("SELECT count(*) FROM operation_corrections WHERE operation_id=$1", oid)[0][0] == 0


def test_given_a_correction_attempt_with_a_forged_status_or_key_then_422_or_ignored_and_the_registry_is_unchanged(client, token_for, world):
    w = world
    oid, _ = treat(client, token_for, w["worker"], w["farm_a"], w["a1"])
    f, h = f"/v1/farms/{w['farm_a']}/operations/{oid}", auth(token_for(w["manager"]))
    assert client.patch(f, headers=h, json={"label_photo_key": "farms/x/labels/y"}).status_code == 422
    assert client.patch(f, headers=h, json={"status": "validated", "note": "n"}).status_code == 200
    assert sql("SELECT status FROM operations WHERE id=$1", oid)[0][0] == "pending_validation"  # only /validate changes the status


def test_given_two_workers_when_one_lists_the_journal_then_only_the_lines_of_their_scope_and_authorship_are_visible(client, token_for, world):
    w = world
    other = new_user()
    sql("INSERT INTO farm_members (farm_id, user_id, role) VALUES ($1,$2,'worker')", w["farm_a"], other)
    assign(w["farm_a"], other, w["a1"])
    mine, _ = treat(client, token_for, w["worker"], w["farm_a"], w["a1"])
    theirs, _ = treat(client, token_for, other, w["farm_a"], w["a1"])
    by_manager, _ = treat(client, token_for, w["manager"], w["farm_a"], w["a1"])
    h = auth(token_for(w["worker"]))
    seen = {i["id"] for i in client.get(f"/v1/farms/{w['farm_a']}/operations", headers=h).json()["items"]}
    assert seen == {str(mine)}
    for hidden in (theirs, by_manager):
        assert client.get(f"/v1/farms/{w['farm_a']}/operations/{hidden}", headers=h).status_code == 404
    assert client.get(f"/v1/farms/{w['farm_a']}/registry", headers=h).status_code == 403


def test_given_a_worker_syncing_an_operation_with_a_validated_status_then_it_stays_pending_while_staff_sync_is_validated(client, token_for, world):
    w = world
    rid_w, rid_o = uuid.uuid4(), uuid.uuid4()
    fields = {"type": "irrigation", "performed_on": TODAY.isoformat(), "parcel_ids": [str(w["a1"])], "status": "validated"}
    worker = client.post("/v1/sync/upload", headers=auth(token_for(w["worker"])), json={"ops": [sync_op("operations", w["farm_a"], rid_w, fields)]})
    owner = client.post("/v1/sync/upload", headers=auth(token_for(w["owner"])), json={"ops": [sync_op("operations", w["farm_a"], rid_o, fields)]})
    assert worker.json()["results"][0]["status"] == "applied" and owner.json()["results"][0]["status"] == "applied"
    assert sql("SELECT status FROM operations WHERE id=$1", rid_w)[0][0] == "pending_validation"
    assert sql("SELECT status FROM operations WHERE id=$1", rid_o)[0][0] == "validated"
    patch = {**sync_op("operations", w["farm_a"], rid_w, {"status": "validated"}, kind="patch"), "base_version": 1}
    assert client.post("/v1/sync/upload", headers=auth(token_for(w["worker"])), json={"ops": [patch]}).status_code == 403
    assert sql("SELECT status FROM operations WHERE id=$1", rid_w)[0][0] == "pending_validation"
