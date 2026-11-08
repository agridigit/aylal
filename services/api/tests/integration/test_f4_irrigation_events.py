"""T059 (US3) - R3-A1..A5: recording an irrigation in one gesture (real PostgreSQL), the linked F6 operation, the recompute, idempotence,
cancellation (never a delete), caps and worker scope. Time is the injected clock (local day 2026-06-04)."""
import uuid

import pytest

from tests.helpers import sql
from tests.integration._f4 import (  # noqa: F401
    FORBIDDEN,
    NOT_FOUND,
    TODAY4,
    YESTERDAY4,
    call,
    compute,
    seed_event,
    world4,
)
from tests.integration._f4_us import advice_url, depleted_parcel


def _url(w, parcel, suffix="irrigation/events"):
    return f"/v1/farms/{w['farm_a']}/parcels/{parcel}/{suffix}"


def _body(**over):
    return {"id": str(uuid.uuid4()), "performed_on": "2026-06-03", "duration_min": 60, **over}


def test_given_a_displayed_advice_when_the_farmer_confirms_done_with_the_advised_duration_then_it_is_recorded_in_one_call(client, token_for, world4):
    w = world4
    parcel = depleted_parcel(w)
    compute(w["farm_a"], parcel)
    advice = call(client, token_for(w["owner"]), "GET", advice_url(w, parcel)).json()
    minutes = advice["sectors"][0]["minutes"]
    r = call(client, token_for(w["owner"]), "POST", _url(w, parcel), _body(performed_on="2026-06-04", duration_min=minutes, sector_no=1))
    assert r.status_code == 201, r.text
    assert r.json()["duration_min"] == minutes and r.json()["status"] == "done" and r.json()["volume_m3"] > 0 and r.json()["net_mm"] > 0


def test_given_a_duration_then_the_volume_is_computed_from_the_installation_and_inversely_for_a_volume(client, token_for, world4):
    w = world4
    parcel = depleted_parcel(w, sectors=1)
    tok = token_for(w["owner"])
    by_duration = call(client, tok, "POST", _url(w, parcel), _body(duration_min=60)).json()
    assert by_duration["input_mode"] == "duration" and by_duration["volume_m3"] > 0
    by_volume = call(client, tok, "POST", _url(w, parcel), _body(duration_min=None, volume_m3=by_duration["volume_m3"])).json()
    assert by_volume["input_mode"] == "volume" and by_volume["duration_min"] == 60


def test_given_both_a_duration_and_a_volume_or_neither_then_422_and_nothing_is_stored(client, token_for, world4):
    w = world4
    tok = token_for(w["owner"])
    for patch in ({"volume_m3": 5}, {"duration_min": None}):
        assert call(client, tok, "POST", _url(w, w["a1"]), _body(**patch)).status_code == 422
    assert sql("SELECT count(*) FROM irrigation_events WHERE parcel_id=$1", w["a1"])[0][0] == 0


def test_given_an_irrigation_when_recorded_then_the_f6_operation_is_created_with_a_server_id_and_appears_in_the_journal_without_double_entry(client, token_for, world4):
    from app.irrigation.ids import operation_id_for

    w = world4
    body = _body()
    r = call(client, token_for(w["owner"]), "POST", _url(w, w["a1"]), body)
    assert r.status_code == 201
    oid = operation_id_for(w["farm_a"], uuid.UUID(body["id"]))
    assert r.json()["operation_id"] == str(oid)
    op = sql("SELECT type, status, author_id FROM operations WHERE id=$1", oid)[0]
    assert (op["type"], op["status"], op["author_id"]) == ("irrigation", "done", w["owner"])
    assert sql("SELECT count(*) FROM operation_parcels WHERE operation_id=$1 AND parcel_id=$2", oid, w["a1"])[0][0] == 1
    journal = call(client, token_for(w["owner"]), "GET", f"/v1/farms/{w['farm_a']}/operations?type=irrigation&parcel_id={w['a1']}&limit=100").json()
    assert [i["id"] for i in journal["items"]].count(str(oid)) == 1
    assert sql("SELECT count(*) FROM operations WHERE farm_id=$1 AND type='irrigation'", w["farm_a"])[0][0] == 1


def test_given_a_client_supplied_operation_id_or_server_field_then_it_is_refused_and_nothing_is_stored(client, token_for, world4):
    w = world4
    for extra in ({"operation_id": str(uuid.uuid4())}, {"author_id": str(w["owner"])}, {"net_mm": 99}, {"farm_id": str(w["farm_b"])}):
        assert call(client, token_for(w["owner"]), "POST", _url(w, w["a1"]), _body(**extra)).status_code == 422
    assert sql("SELECT count(*) FROM irrigation_events WHERE parcel_id=$1", w["a1"])[0][0] == 0


def test_given_the_same_id_replayed_then_the_second_call_is_a_200_without_any_new_row(client, token_for, world4):
    w = world4
    body, tok = _body(), token_for(w["owner"])
    assert call(client, tok, "POST", _url(w, w["a1"]), body).status_code == 201
    again = call(client, tok, "POST", _url(w, w["a1"]), body)
    assert again.status_code == 200 and again.json()["id"] == body["id"]
    assert sql("SELECT count(*) FROM irrigation_events WHERE id=$1", uuid.UUID(body["id"]))[0][0] == 1
    assert sql("SELECT count(*) FROM operations WHERE farm_id=$1 AND type='irrigation'", w["farm_a"])[0][0] == 1
    assert sql("SELECT count(*) FROM irrigation_applied WHERE parcel_id=$1", w["a1"])[0][0] == 1


def test_given_an_id_of_another_farm_then_the_answer_is_the_same_404_and_nothing_leaks(client, token_for, world4):
    w = world4
    body = _body()
    assert call(client, token_for(w["owner_b"]), "POST", _url({**w, "farm_a": w["farm_b"]}, w["b1"]), body).status_code == 201
    other = call(client, token_for(w["owner"]), "POST", _url(w, w["a1"]), body)
    assert other.status_code == 404 and other.json() == NOT_FOUND


def test_given_two_distinct_entries_on_the_same_day_and_sector_then_both_are_kept_and_the_second_is_flagged_possible_duplicate(client, token_for, world4):
    w = world4
    tok = token_for(w["owner"])
    first = call(client, tok, "POST", _url(w, w["a1"]), _body(sector_no=1)).json()
    second = call(client, tok, "POST", _url(w, w["a1"]), _body(sector_no=1)).json()
    assert first["possible_duplicate"] is False and second["possible_duplicate"] is True
    assert sql("SELECT count(*) FROM irrigation_events WHERE parcel_id=$1 AND status='done'", w["a1"])[0][0] == 2


def test_given_a_recorded_irrigation_when_the_balance_is_recomputed_then_the_day_and_the_next_advice_account_for_it(client, token_for, world4):
    w = world4
    parcel = depleted_parcel(w, "Recalc")
    compute(w["farm_a"], parcel)
    before = call(client, token_for(w["owner"]), "GET", f"/v1/farms/{w['farm_a']}/parcels/{parcel}/irrigation/balance").json()["days"][-1]
    event = call(client, token_for(w["owner"]), "POST", _url(w, parcel), _body(duration_min=240, sector_no=1)).json()
    compute(w["farm_a"], parcel)
    after = call(client, token_for(w["owner"]), "GET", f"/v1/farms/{w['farm_a']}/parcels/{parcel}/irrigation/balance").json()["days"]
    day = next(d for d in after if d["day"] == "2026-06-03")
    assert abs(day["irrigation_net_mm"] - event["net_mm"]) < 0.01
    assert after[-1]["depletion_mm"] < before["depletion_mm"]


def test_given_backdated_entries_then_one_recompute_job_per_parcel_keeps_the_oldest_date(client, token_for, world4):
    w = world4
    tok = token_for(w["owner"])
    for day in ("2026-06-02", "2026-05-20", "2026-06-03"):
        assert call(client, tok, "POST", _url(w, w["a1"]), _body(performed_on=day)).status_code == 201
    jobs = sql("SELECT from_date FROM irrigation_jobs WHERE parcel_id=$1 AND state='queued'", w["a1"])
    assert len(jobs) == 1 and str(jobs[0][0]) == "2026-05-20"


@pytest.mark.parametrize("patch", [{"performed_on": "2026-06-05"}, {"performed_on": "2025-04-29"}, {"duration_min": 1441}, {"duration_min": 0}])
def test_given_a_future_a_too_old_or_an_excessive_entry_then_422_and_nothing_is_stored(client, token_for, world4, patch):
    w = world4
    r = call(client, token_for(w["owner"]), "POST", _url(w, w["a1"]), _body(**patch))
    assert r.status_code == 422, r.text
    assert sql("SELECT count(*) FROM irrigation_events WHERE parcel_id=$1", w["a1"])[0][0] == 0


def test_given_24_events_on_the_day_and_sector_then_the_25th_is_refused(client, token_for, world4):
    w = world4
    for _ in range(24):
        seed_event(w["farm_a"], w["a1"], w["owner"], day=YESTERDAY4)
    r = call(client, token_for(w["owner"]), "POST", _url(w, w["a1"]), _body(performed_on="2026-06-03"))
    assert r.status_code == 409 and r.json()["detail"] == "quota_exceeded"


def test_given_a_cancellation_then_the_event_and_its_operation_are_cancelled_never_deleted_and_the_applied_water_leaves_the_totals(client, token_for, world4):
    w = world4
    tok = token_for(w["owner"])
    event = call(client, tok, "POST", _url(w, w["a1"]), _body()).json()
    r = call(client, tok, "POST", _url(w, w["a1"], f"irrigation/events/{event['id']}/cancel"))
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
    assert sql("SELECT status FROM operations WHERE id=$1", uuid.UUID(event["operation_id"]))[0][0] == "cancelled"
    assert sql("SELECT count(*) FROM irrigation_events WHERE id=$1", uuid.UUID(event["id"]))[0][0] == 1
    assert sql("SELECT count(*) FROM irrigation_applied WHERE id=$1", uuid.UUID(event["id"]))[0][0] == 0
    assert call(client, tok, "POST", _url(w, w["a1"], f"irrigation/events/{event['id']}/cancel")).status_code == 200  # idempotent
    assert call(client, tok, "POST", _url(w, w["a1"]), {**_body(), "id": event["id"]}).json()["status"] == "cancelled"  # a replay never resurrects it
    assert sql("SELECT count(*) FROM irrigation_jobs WHERE parcel_id=$1 AND state='queued'", w["a1"])[0][0] == 1


def test_given_the_applied_view_then_it_carries_neither_an_author_nor_a_note(client, token_for, world4):
    w = world4
    call(client, token_for(w["owner"]), "POST", _url(w, w["a1"]), _body(note="private remark"))
    cols = {r[0] for r in sql("SELECT column_name FROM information_schema.columns WHERE table_name='irrigation_applied'")}
    assert not cols & {"author_id", "note", "created_by"}
    assert sql("SELECT count(*) FROM irrigation_applied WHERE parcel_id=$1", w["a1"])[0][0] == 1


def test_given_a_worker_then_they_record_on_an_assigned_parcel_list_only_their_own_events_and_cancel_only_their_own(client, token_for, world4):
    w = world4
    tok = token_for(w["worker"])
    mine = call(client, tok, "POST", _url(w, w["a1"]), _body()).json()
    theirs = seed_event(w["farm_a"], w["a1"], w["owner"])
    listed = call(client, tok, "GET", _url(w, w["a1"])).json()["items"]
    assert [i["id"] for i in listed] == [mine["id"]]
    assert call(client, tok, "POST", _url(w, w["a1"], f"irrigation/events/{theirs}/cancel")).json() == FORBIDDEN
    assert call(client, tok, "POST", _url(w, w["a1"], f"irrigation/events/{mine['id']}/cancel")).status_code == 200


def test_given_a_hidden_archived_or_unknown_parcel_then_the_worker_gets_the_same_404_when_recording(client, token_for, world4):
    w = world4
    sql("UPDATE parcels SET archived_at=now() WHERE id=$1", w["p"][2])
    tok = token_for(w["worker"])
    answers = [call(client, tok, "POST", _url(w, p), _body()) for p in (w["hidden"], uuid.uuid4(), w["p"][2])]
    assert {(a.status_code, str(a.json())) for a in answers} == {(404, str(NOT_FOUND))}
    assert sql("SELECT count(*) FROM irrigation_events WHERE parcel_id = ANY($1)", [w["hidden"], w["p"][2]])[0][0] == 0
