"""T060 (US3) - R3-A4, SC-005: events recorded offline are replayed through /v1/sync/upload without loss, idempotently, with the
server-owned fields derived; a cancellation is the only patch."""
import uuid

from tests.helpers import sql
from tests.integration._f4 import call, seed_event, sync_event, sync_op, sync_post, world4  # noqa: F401


def test_given_thirty_days_recorded_offline_when_replayed_in_batches_twice_then_nothing_is_lost_or_duplicated(client, token_for, world4):
    w = world4
    tok = token_for(w["worker"])
    days = [f"2026-05-{d:02d}" for d in range(5, 31)] + [f"2026-06-{d:02d}" for d in range(1, 5)]
    ops = [sync_event(w["farm_a"], w["a1"], performed_on=day) for day in days]
    assert len(ops) == 30
    for i in range(0, 30, 10):
        r = sync_post(client, tok, ops[i:i + 10])
        assert r.status_code == 200 and {x["status"] for x in r.json()["results"]} == {"applied"}, r.text
    again = sync_post(client, tok, ops)
    assert again.status_code == 200 and {x["status"] for x in again.json()["results"]} == {"duplicate"}
    assert sql("SELECT count(*) FROM irrigation_events WHERE parcel_id=$1", w["a1"])[0][0] == 30
    assert sql("SELECT count(*) FROM operations WHERE farm_id=$1 AND type='irrigation'", w["farm_a"])[0][0] == 30


def test_given_the_same_record_sent_under_a_new_op_id_then_the_event_is_still_stored_once(client, token_for, world4):
    w, rid = world4, uuid.uuid4()
    tok = token_for(w["owner"])
    assert sync_post(client, tok, [sync_event(w["farm_a"], w["a1"], rid)]).status_code == 200
    r = sync_post(client, tok, [sync_event(w["farm_a"], w["a1"], rid)])
    assert r.json()["results"][0]["status"] == "duplicate"
    assert sql("SELECT count(*) FROM irrigation_events WHERE id=$1", rid)[0][0] == 1
    assert sql("SELECT count(*) FROM operations WHERE farm_id=$1 AND type='irrigation'", w["farm_a"])[0][0] == 1


def test_given_an_event_written_offline_then_the_volume_and_the_net_depth_are_derived_by_the_server(client, token_for, world4):
    w, rid = world4, uuid.uuid4()
    assert sync_post(client, token_for(w["owner"]), [sync_event(w["farm_a"], w["a1"], rid, duration_min=90)]).status_code == 200
    row = sql("SELECT volume_m3, net_mm, duration_min FROM irrigation_events WHERE id=$1", rid)[0]
    assert row["duration_min"] == 90 and row["volume_m3"] is not None and row["net_mm"] is not None


def test_given_a_cancellation_patch_then_the_event_is_cancelled_and_any_other_patch_is_rejected(client, token_for, world4):
    w = world4
    eid = seed_event(w["farm_a"], w["a1"], w["owner"])
    tok = token_for(w["owner"])
    bad = sync_post(client, tok, [sync_op("irrigation_events", w["farm_a"], eid, {"duration_min": 1}, kind="patch")])
    assert bad.json()["results"][0]["status"] == "rejected" and sql("SELECT duration_min FROM irrigation_events WHERE id=$1", eid)[0][0] == 60
    ok = sync_post(client, tok, [sync_op("irrigation_events", w["farm_a"], eid, {"status": "cancelled"}, kind="patch")])
    assert ok.json()["results"][0]["status"] == "applied" and sql("SELECT status FROM irrigation_events WHERE id=$1", eid)[0][0] == "cancelled"


def test_given_a_hidden_or_foreign_parcel_when_uploading_then_the_event_is_refused_and_nothing_is_written(client, token_for, world4):
    w = world4
    rid = uuid.uuid4()
    res = sync_post(client, token_for(w["worker"]), [sync_event(w["farm_a"], w["hidden"], rid)])
    assert res.status_code in (200, 403, 404) and (res.status_code != 200 or res.json()["results"][0]["status"] == "rejected")
    foreign = sync_post(client, token_for(w["owner_b"]), [sync_event(w["farm_a"], w["a1"], uuid.uuid4())])
    assert foreign.status_code == 404
    assert sql("SELECT count(*) FROM irrigation_events WHERE parcel_id=ANY($1)", [w["hidden"]])[0][0] == 0
