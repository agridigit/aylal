"""T060 - R4-A1, R4-A3, R4-A4: planned operations, reminders, mark_done, reschedule, cancel, 500 cap, worker scope."""
import datetime as dt
import uuid

from tests.helpers import auth, sql
from tests.integration._f6 import TODAY, add_operation, op_body, world  # noqa: F401
from tests.integration._f6_phyto import add_catalog, add_product, crops, grow

SOON = TODAY + dt.timedelta(days=1)


def api(client, token_for, who, method, path, body=None):
    return client.request(method, path, headers=auth(token_for(who)), json=body)


def plan(client, token_for, w, who="owner", parcel="a1", **kw):
    r = api(client, token_for, w[who], "POST", f"/v1/farms/{w['farm_a']}/operations", op_body([w[parcel]], performed_on=SOON.isoformat(), **kw))
    assert r.status_code == 201, r.text
    return r.json()


def test_given_a_future_date_when_recording_then_the_status_is_planned_for_every_role_with_a_scheduled_reminder(client, token_for, world):
    w = world
    for who in ("owner", "manager", "worker"):
        out = plan(client, token_for, w, who)
        assert out["status"] == "planned" and out["overdue"] is False
        rem = sql("SELECT fire_on, state FROM operation_reminders WHERE operation_id=$1", uuid.UUID(out["id"]))
        assert [(r["fire_on"], r["state"]) for r in rem] == [(SOON, "scheduled")]


def test_given_a_planned_phyto_treatment_then_nothing_is_written_to_the_registry_until_it_is_done(client, token_for, world):
    w = world
    out = plan(client, token_for, w, type="phyto", free_product_name="Maison", dose=1, dose_unit="L/ha")
    assert sql("SELECT count(*) FROM registry_entries WHERE operation_id=$1", uuid.UUID(out["id"]))[0][0] == 0


def test_given_a_planned_operation_when_marked_done_then_it_counts_in_the_journal_the_registry_and_the_reminder_is_closed(client, token_for, world):
    w = world
    (cid, slug), = crops(1)
    grow(w["farm_a"], w["a1"], cid)
    product = add_product(add_catalog(), "Cuprex", [dict(crop_slug=slug, max_dose=5, dar_days=7)])
    out = plan(client, token_for, w, type="phyto", product_id=str(product), dose=1, dose_unit="L/ha")
    done = api(client, token_for, w["owner"], "POST", f"/v1/farms/{w['farm_a']}/operations/{out['id']}/done")
    assert done.status_code == 200 and done.json()["status"] == "validated"
    assert [r[0] for r in sql("SELECT entry_kind FROM registry_current WHERE operation_id=$1", uuid.UUID(out["id"]))] == ["application"]
    assert sql("SELECT state FROM operation_reminders WHERE operation_id=$1", uuid.UUID(out["id"]))[0][0] == "done"
    listed = api(client, token_for, w["owner"], "GET", f"/v1/farms/{w['farm_a']}/operations?status=validated").json()["items"]
    assert [i["id"] for i in listed] == [out["id"]]
    assert api(client, token_for, w["owner"], "GET", f"/v1/farms/{w['farm_a']}/fields/{w['a1']}/earliest-harvest").json()["date"] is not None


def test_given_a_worker_planned_operation_when_marked_done_by_its_author_then_it_awaits_validation(client, token_for, world):
    w = world
    out = plan(client, token_for, w, "worker")
    done = api(client, token_for, w["worker"], "POST", f"/v1/farms/{w['farm_a']}/operations/{out['id']}/done")
    assert done.status_code == 200 and done.json()["status"] == "pending_validation"


def test_given_a_done_operation_when_marking_done_again_then_409_and_nothing_changes(client, token_for, world):
    w = world
    out = plan(client, token_for, w)
    url = f"/v1/farms/{w['farm_a']}/operations/{out['id']}/done"
    assert api(client, token_for, w["owner"], "POST", url).status_code == 200
    assert api(client, token_for, w["owner"], "POST", url).status_code == 409
    assert sql("SELECT count(*) FROM registry_entries")[0][0] == 0


def test_given_a_planned_operation_when_cancelled_then_it_is_cancelled_the_reminder_dismissed_and_the_registry_untouched(client, token_for, world):
    w = world
    out = plan(client, token_for, w, type="phyto", free_product_name="Maison", dose=1, dose_unit="L/ha")
    r = api(client, token_for, w["owner"], "POST", f"/v1/farms/{w['farm_a']}/operations/{out['id']}/cancel")
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
    assert sql("SELECT state FROM operation_reminders WHERE operation_id=$1", uuid.UUID(out["id"]))[0][0] == "dismissed"
    assert sql("SELECT count(*) FROM registry_entries WHERE operation_id=$1", uuid.UUID(out["id"]))[0][0] == 0
    assert api(client, token_for, w["owner"], "POST", f"/v1/farms/{w['farm_a']}/operations/{out['id']}/done").status_code == 409


def test_given_an_overdue_planned_operation_then_it_stays_visible_as_overdue_and_can_be_done_cancelled_or_rescheduled(client, token_for, world):
    w = world
    oid = add_operation(w["farm_a"], w["owner"], w["a1"], status="planned", performed_on=TODAY - dt.timedelta(days=2))
    got = api(client, token_for, w["owner"], "GET", f"/v1/farms/{w['farm_a']}/operations/{oid}").json()
    assert got["status"] == "planned" and got["overdue"] is True
    items = api(client, token_for, w["owner"], "GET", f"/v1/farms/{w['farm_a']}/operations?status=planned").json()["items"]
    assert [i["id"] for i in items] == [str(oid)] and items[0]["overdue"] is True


def test_given_an_overdue_planned_operation_when_rescheduled_to_a_future_date_then_it_moves_and_the_reminder_follows(client, token_for, world):
    w = world
    out = plan(client, token_for, w, "worker")
    sql("UPDATE operations SET performed_on=$2 WHERE id=$1", uuid.UUID(out["id"]), TODAY - dt.timedelta(days=2))
    target = TODAY + dt.timedelta(days=5)
    r = api(client, token_for, w["worker"], "POST", f"/v1/farms/{w['farm_a']}/operations/{out['id']}/reschedule", {"performed_on": target.isoformat()})
    assert r.status_code == 200, r.text
    assert r.json()["performed_on"] == target.isoformat() and r.json()["status"] == "planned" and r.json()["overdue"] is False
    assert [(x["fire_on"], x["state"]) for x in sql("SELECT fire_on, state FROM operation_reminders WHERE operation_id=$1", uuid.UUID(out["id"]))] == [(target, "scheduled")]
    assert sql("SELECT performed_on FROM operation_parcels WHERE operation_id=$1", uuid.UUID(out["id"]))[0][0] == target


def test_given_a_past_date_or_a_non_planned_operation_when_rescheduling_then_422_or_409(client, token_for, world):
    w = world
    out = plan(client, token_for, w)
    url = f"/v1/farms/{w['farm_a']}/operations/{out['id']}/reschedule"
    assert api(client, token_for, w["owner"], "POST", url, {"performed_on": (TODAY - dt.timedelta(days=1)).isoformat()}).status_code == 422
    assert api(client, token_for, w["owner"], "POST", url, {"performed_on": SOON.isoformat(), "status": "validated"}).status_code == 422
    done = add_operation(w["farm_a"], w["owner"], w["a1"], status="validated")
    assert api(client, token_for, w["owner"], "POST", f"/v1/farms/{w['farm_a']}/operations/{done}/reschedule", {"performed_on": SOON.isoformat()}).status_code == 409


def test_given_a_worker_when_rescheduling_or_acting_on_someone_elses_planned_operation_then_403_and_nothing_changes(client, token_for, world):
    w = world
    theirs = plan(client, token_for, w, "manager")
    for method, suffix, body in (("POST", "reschedule", {"performed_on": (TODAY + dt.timedelta(days=9)).isoformat()}), ("POST", "done", None), ("POST", "cancel", None)):
        assert api(client, token_for, w["worker"], method, f"/v1/farms/{w['farm_a']}/operations/{theirs['id']}/{suffix}", body).status_code == 403, suffix
    row = sql("SELECT status, performed_on FROM operations WHERE id=$1", uuid.UUID(theirs["id"]))[0]
    assert (row["status"], row["performed_on"]) == ("planned", SOON)


def test_given_a_reschedule_of_an_operation_of_another_farm_or_an_unassigned_parcel_then_404(client, token_for, world):
    w = world
    foreign = add_operation(w["farm_b"], w["owner_b"], w["b1"], status="planned", performed_on=SOON)
    body = {"performed_on": (TODAY + dt.timedelta(days=3)).isoformat()}
    assert api(client, token_for, w["owner"], "POST", f"/v1/farms/{w['farm_a']}/operations/{foreign}/reschedule", body).status_code == 404
    hidden = add_operation(w["farm_a"], w["worker"], w["a2"], status="planned", performed_on=SOON)
    assert api(client, token_for, w["worker"], "POST", f"/v1/farms/{w['farm_a']}/operations/{hidden}/reschedule", body).status_code == 404
    assert api(client, token_for, w["outsider"], "POST", f"/v1/farms/{w['farm_a']}/operations/{hidden}/reschedule", body).status_code == 404


def test_given_planned_operations_then_a_worker_sees_only_their_own_on_assigned_parcels_and_staff_see_all(client, token_for, world):
    w = world
    mine = plan(client, token_for, w, "worker")
    plan(client, token_for, w, "manager")
    add_operation(w["farm_a"], w["worker"], w["a2"], status="planned", performed_on=SOON)
    seen = api(client, token_for, w["worker"], "GET", f"/v1/farms/{w['farm_a']}/operations?status=planned").json()["items"]
    assert [i["id"] for i in seen] == [mine["id"]]
    assert len(api(client, token_for, w["owner"], "GET", f"/v1/farms/{w['farm_a']}/operations?status=planned").json()["items"]) == 3
    sql("UPDATE parcels SET archived_at=now() WHERE id=$1", w["a1"])
    assert api(client, token_for, w["worker"], "GET", f"/v1/farms/{w['farm_a']}/operations?status=planned").json()["items"] == []


def _seed_planned(farm, author, parcel, n):
    sql("INSERT INTO operations (id, farm_id, type, performed_on, status, author_id) "
        "SELECT gen_random_uuid(), $1, 'irrigation', current_date + 1 + (g % 300), 'planned', $2 FROM generate_series(1, $3) g", farm, author, n)


def test_given_500_planned_operations_when_planning_one_more_then_413_planned_quota_exceeded_and_a_done_one_frees_a_slot(client, token_for, world):
    w = world
    _seed_planned(w["farm_a"], w["owner"], w["a1"], 500)
    over = api(client, token_for, w["owner"], "POST", f"/v1/farms/{w['farm_a']}/operations", op_body([w["a1"]], performed_on=SOON.isoformat()))
    assert over.status_code == 413 and over.json()["detail"]["code"] == "planned_quota_exceeded"
    assert sql("SELECT count(*) FROM operations WHERE farm_id=$1", w["farm_a"])[0][0] == 500
    # a past-dated (not planned) operation is not limited by the planned cap
    assert api(client, token_for, w["owner"], "POST", f"/v1/farms/{w['farm_a']}/operations", op_body([w["a1"]])).status_code == 201
    sql("UPDATE operations SET status='cancelled' WHERE id=(SELECT id FROM operations WHERE farm_id=$1 AND status='planned' LIMIT 1)", w["farm_a"])
    assert api(client, token_for, w["owner"], "POST", f"/v1/farms/{w['farm_a']}/operations", op_body([w["a1"]], performed_on=SOON.isoformat())).status_code == 201


def test_given_the_planned_cap_of_one_farm_then_another_farm_can_still_plan(client, token_for, world):
    w = world
    _seed_planned(w["farm_a"], w["owner"], w["a1"], 500)
    r = api(client, token_for, w["owner_b"], "POST", f"/v1/farms/{w['farm_b']}/operations", op_body([w["b1"]], performed_on=SOON.isoformat()))
    assert r.status_code == 201
