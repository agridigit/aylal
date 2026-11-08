"""T016 - G1: 403 by role on a visible parcel; 404 identical when the parcel is not visible to the worker."""

import pytest

from tests.helpers import sql
from tests.integration._f3 import NOT_FOUND, call, seed_alert, seed_scene, seed_zone, world3  # noqa: F401

JPEG = b"\xff\xd8\xff\xe0" + b"0" * 512


def _paths(w, parcel):
    f = f"/v1/farms/{w['farm_a']}"
    a, z = seed_alert(w["farm_a"], parcel), seed_zone(w["farm_a"], parcel)
    return {"alert.dismiss": ("POST", f"{f}/alerts/{a}/dismiss", None), "zone.dismiss": ("POST", f"{f}/zones/{z}/dismiss", None),
            "imagery.reprocess": ("POST", f"{f}/parcels/{parcel}/vigor/reprocess", None)}, z


@pytest.mark.parametrize("action", ["alert.dismiss", "zone.dismiss", "imagery.reprocess"])
def test_given_a_worker_on_an_assigned_parcel_when_doing_a_staff_action_then_403(client, token_for, world3, action):
    w = world3
    paths, _ = _paths(w, w["a1"])
    m, p, b = paths[action]
    assert call(client, token_for(w["owner"]), *(("GET", f"/v1/farms/{w['farm_a']}/alerts", None))).status_code == 200
    r = call(client, token_for(w["worker"]), m, p, b)
    assert r.status_code == 403 and r.json() == {"detail": "forbidden"}, r.text


@pytest.mark.parametrize("action", ["alert.dismiss", "zone.dismiss", "imagery.reprocess"])
@pytest.mark.parametrize("who", ["owner", "manager"])
def test_given_owner_or_manager_when_doing_a_staff_action_then_it_succeeds(client, token_for, world3, action, who):
    w = world3
    paths, _ = _paths(w, w["a1"])
    m, p, b = paths[action]
    r = call(client, token_for(w[who]), m, p, b)
    assert r.status_code in (200, 202), r.text


@pytest.mark.parametrize("kind", ["unassigned", "archived", "unknown"])
def test_given_a_worker_on_a_parcel_not_visible_to_them_then_404_identical_to_an_unknown_parcel(client, token_for, world3, kind):
    w = world3
    tok = token_for(w["worker"])
    assert call(client, tok, "GET", f"/v1/farms/{w['farm_a']}/parcels/{w['a1']}/status").status_code == 200
    if kind == "archived":
        sql("UPDATE parcels SET archived_at=now() WHERE id=$1", w["a1"])
        parcel = w["a1"]
    elif kind == "unassigned":
        parcel = w["hidden"]
    else:
        import uuid
        parcel = uuid.uuid4()
    paths, _z = _paths(w, parcel) if kind != "unknown" else ({}, None)
    f = f"/v1/farms/{w['farm_a']}"
    for method, path in (("GET", f"{f}/parcels/{parcel}/status"), ("GET", f"{f}/parcels/{parcel}/vigor"), ("POST", f"{f}/parcels/{parcel}/vigor/reprocess")):
        r = call(client, tok, method, path)
        assert r.status_code == 404 and r.json() == NOT_FOUND, (kind, path, r.text)
    for m, p, b in paths.values():
        r = call(client, tok, m, p, b)
        assert r.status_code == 404 and r.json() == NOT_FOUND, (kind, p, r.text)


def test_given_a_worker_when_observing_then_only_an_assigned_parcel_zone_is_allowed(client, token_for, world3):
    import uuid

    w = world3
    tok = token_for(w["worker"])
    mine, theirs = seed_zone(w["farm_a"], w["a1"]), seed_zone(w["farm_a"], w["hidden"])
    f = f"/v1/farms/{w['farm_a']}/zones"
    ok = call(client, tok, "POST", f"{f}/{mine}/observations", {"id": str(uuid.uuid4()), "note": "vu"})
    assert ok.status_code == 201, ok.text
    no = call(client, tok, "POST", f"{f}/{theirs}/observations", {"id": str(uuid.uuid4()), "note": "vu"})
    assert no.status_code == 404 and no.json() == NOT_FOUND
    assert sql("SELECT count(*) FROM zone_observations WHERE zone_id=$1", theirs)[0][0] == 0
