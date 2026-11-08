"""T018 - G1: 403 by role on a visible parcel; 404 identical when the parcel is not visible; worker corrections limited to own events."""
import uuid

import pytest

from tests.helpers import sql
from tests.integration._f4 import (  # noqa: F401
    FORBIDDEN,
    NOT_FOUND,
    SYSTEM_BODY,
    call,
    seed_analysis,
    seed_event,
    world4,
)


def _f(w, parcel):
    return f"/v1/farms/{w['farm_a']}/parcels/{parcel}"


WORKER_403 = [("PUT", "irrigation-system", SYSTEM_BODY), ("GET", "irrigation-system/versions", None), ("GET", "water-analyses", None),
              ("POST", "water-analyses", {"id": str(uuid.uuid4()), "ec_ds_m": 2.0, "analysed_on": "2026-06-01"})]


@pytest.mark.parametrize("method,suffix,body", WORKER_403, ids=lambda x: x if isinstance(x, str) else "")
def test_given_a_worker_on_an_assigned_parcel_when_doing_a_staff_action_then_403(client, token_for, world4, method, suffix, body):
    w = world4
    assert call(client, token_for(w["owner"]), "GET", f"{_f(w, w['a1'])}/irrigation-system").status_code == 200
    r = call(client, token_for(w["worker"]), method, f"{_f(w, w['a1'])}/{suffix}", body)
    assert r.status_code == 403 and r.json() == FORBIDDEN, r.text


@pytest.mark.parametrize("who", ["owner", "manager"])
def test_given_staff_when_doing_staff_actions_then_they_succeed(client, token_for, world4, who):
    w = world4
    tok = token_for(w[who])
    assert call(client, tok, "PUT", f"{_f(w, w['a1'])}/irrigation-system", SYSTEM_BODY).status_code == 200
    assert call(client, tok, "GET", f"{_f(w, w['a1'])}/water-analyses").status_code == 200
    assert call(client, tok, "POST", f"{_f(w, w['a1'])}/water-analyses", {"id": str(uuid.uuid4()), "ec_ds_m": 2.0, "analysed_on": "2026-06-01"}).status_code == 201


def test_given_a_worker_when_recording_on_an_assigned_parcel_then_it_is_allowed_and_the_author_is_the_server_user(client, token_for, world4):
    w = world4
    eid = uuid.uuid4()
    r = call(client, token_for(w["worker"]), "POST", f"{_f(w, w['a1'])}/irrigation/events", {"id": str(eid), "performed_on": "2026-06-03", "duration_min": 30})
    assert r.status_code == 201, r.text
    assert sql("SELECT author_id FROM irrigation_events WHERE id=$1", eid)[0][0] == w["worker"]


def test_given_a_worker_when_cancelling_then_only_their_own_event_is_allowed_otherwise_403(client, token_for, world4):
    w = world4
    mine = seed_event(w["farm_a"], w["a1"], w["worker"])
    theirs = seed_event(w["farm_a"], w["a1"], w["owner"])
    tok = token_for(w["worker"])
    r = call(client, tok, "POST", f"{_f(w, w['a1'])}/irrigation/events/{theirs}/cancel")
    assert r.status_code == 403 and r.json() == FORBIDDEN and sql("SELECT status FROM irrigation_events WHERE id=$1", theirs)[0][0] == "done"
    assert call(client, tok, "POST", f"{_f(w, w['a1'])}/irrigation/events/{mine}/cancel").status_code == 200
    assert sql("SELECT status FROM irrigation_events WHERE id=$1", mine)[0][0] == "cancelled"
    assert call(client, token_for(w["manager"]), "POST", f"{_f(w, w['a1'])}/irrigation/events/{theirs}/cancel").status_code == 200


def test_given_a_worker_listing_events_then_only_their_own_are_returned(client, token_for, world4):
    w = world4
    mine = seed_event(w["farm_a"], w["a1"], w["worker"])
    seed_event(w["farm_a"], w["a1"], w["owner"])
    r = call(client, token_for(w["worker"]), "GET", f"{_f(w, w['a1'])}/irrigation/events")
    assert r.status_code == 200 and [e["id"] for e in r.json()["items"]] == [str(mine)]
    assert len(call(client, token_for(w["owner"]), "GET", f"{_f(w, w['a1'])}/irrigation/events").json()["items"]) == 2


@pytest.mark.parametrize("kind", ["unassigned", "archived", "unknown"])
def test_given_a_worker_on_a_parcel_not_visible_to_them_then_404_identical_on_every_parcel_route(client, token_for, world4, kind):
    w = world4
    tok = token_for(w["worker"])
    assert call(client, tok, "GET", f"{_f(w, w['a1'])}/irrigation/advice").status_code == 200
    if kind == "archived":
        sql("UPDATE parcels SET archived_at=now() WHERE id=$1", w["a1"])
        parcel = w["a1"]
    else:
        parcel = w["hidden"] if kind == "unassigned" else uuid.uuid4()
    ev = seed_event(w["farm_a"], w["hidden"], w["owner"]) if kind != "unknown" else uuid.uuid4()
    for method, suffix, body in [("GET", "irrigation-system", None), ("PUT", "irrigation-system", SYSTEM_BODY), ("GET", "irrigation/advice", None),
                                 ("GET", "irrigation/balance", None), ("GET", "irrigation/events", None), ("GET", "water-analyses", None),
                                 ("POST", "irrigation/events", {"id": str(uuid.uuid4()), "performed_on": "2026-06-03", "duration_min": 30}),
                                 ("POST", f"irrigation/events/{ev}/cancel", None)]:
        r = call(client, tok, method, f"{_f(w, parcel)}/{suffix}", body)
        assert r.status_code == 404 and r.json() == NOT_FOUND, (kind, method, suffix, r.status_code, r.text)
    assert sql("SELECT count(*) FROM irrigation_events WHERE parcel_id=$1 AND author_id=$2", parcel, w["worker"])[0][0] == 0


def test_given_a_rainfed_parcel_when_writing_an_installation_then_422(client, token_for, world4):
    w = world4
    sql("UPDATE parcels SET irrigation='rainfed' WHERE id=$1", w["p"][8])
    r = call(client, token_for(w["owner"]), "PUT", f"{_f(w, w['p'][8])}/irrigation-system", SYSTEM_BODY)
    assert r.status_code == 422, r.text
