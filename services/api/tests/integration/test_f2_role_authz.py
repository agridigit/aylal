"""T006 - role authorization (403) and worker visibility (404) on F2 routes (guardrail 2, FR-020)."""
import uuid

import pytest

from tests.helpers import auth, sql
from tests.integration._f2 import (
    add_custom_crop, add_field, add_season, assign, new_user, reference_crop, square,
)


@pytest.fixture
def world(make_farm):
    owner, manager, worker = new_user(), new_user(), new_user()
    farm = make_farm({owner: "owner", manager: "manager", worker: "worker"})
    mine, other = add_field(farm, "Mine"), add_field(farm, "Other", lon=-7.5)
    assign(farm, worker, mine)
    return dict(owner=owner, manager=manager, worker=worker, farm=farm, mine=mine, other=other,
                season_mine=add_season(farm, mine), season_other=add_season(farm, other))


def req(client, token_for, who, method, path, body=None):
    return client.request(method, path, headers=auth(token_for(who)), json=body)


def management(w):
    f, m = f"/v1/farms/{w['farm']}", w["mine"]
    return [
        ("POST", f"{f}/fields", {"name": "N", "geometry": square(-7.7)}),
        ("PATCH", f"{f}/fields/{m}", {"name": "Hacked"}),
        ("DELETE", f"{f}/fields/{m}", None),
        ("POST", f"{f}/fields/{m}/restore", None),
        ("POST", f"{f}/fields/merge", {"survivor_id": str(m), "merged_ids": [str(w["other"])]}),
        ("POST", f"{f}/fields/{m}/blocks", {"name": "b", "kind": "block", "geometry": square(-7.6, 33.57, 0.0005)}),
        ("POST", f"{f}/fields/{m}/seasons", {"crop_id": str(reference_crop()), "started_at": "2026-01-01"}),
        ("PATCH", f"{f}/fields/{m}/seasons/{w['season_mine']}", {"stage_corrected": "flowering"}),
        ("POST", f"{f}/crops", {"name": "Safran", "cycle": "annual"}),
    ]


def test_given_a_worker_when_managing_an_assigned_field_then_403_and_nothing_changes(client, token_for, world):
    w = world
    for m, p, b in management(w):
        assert req(client, token_for, w["worker"], m, p, b).status_code == 403, f"{m} {p}"
    assert sql("SELECT name, archived_at FROM parcels WHERE id=$1", w["mine"])[0][:] == ("Mine", None)
    assert sql("SELECT count(*) FROM parcels WHERE farm_id=$1", w["farm"])[0][0] == 2
    assert sql("SELECT count(*) FROM crops WHERE farm_id=$1", w["farm"])[0][0] == 0


def test_given_a_worker_when_reading_an_unassigned_field_then_404_not_403(client, token_for, world):
    w = world
    f, o = f"/v1/farms/{w['farm']}", w["other"]
    for m, p, b in [
        ("GET", f"{f}/fields/{o}", None),
        ("PATCH", f"{f}/fields/{o}", {"name": "Hacked"}),
        ("DELETE", f"{f}/fields/{o}", None),
        ("GET", f"{f}/fields/{o}/blocks", None),
        ("POST", f"{f}/fields/{o}/blocks", {"name": "b", "kind": "block", "geometry": square(-7.5, 33.57, 0.0005)}),
        ("GET", f"{f}/fields/{o}/seasons", None),
        ("POST", f"{f}/fields/{o}/seasons", {"crop_id": str(reference_crop()), "started_at": "2026-01-01"}),
        ("GET", f"{f}/fields/{o}/seasons/{w['season_other']}", None),
        ("GET", f"{f}/fields/archived", None),
    ]:
        assert req(client, token_for, w["worker"], m, p, b).status_code == 404, f"{m} {p}"


def test_given_a_worker_when_reading_an_assigned_field_then_200_and_the_list_has_only_assigned_fields(client, token_for, world):
    w = world
    f = f"/v1/farms/{w['farm']}"
    assert req(client, token_for, w["worker"], "GET", f"{f}/fields/{w['mine']}").status_code == 200
    assert req(client, token_for, w["worker"], "GET", f"{f}/fields/{w['mine']}/seasons").status_code == 200
    assert req(client, token_for, w["worker"], "GET", f"{f}/fields/{w['mine']}/blocks").status_code == 200
    r = req(client, token_for, w["worker"], "GET", f"{f}/fields")
    assert r.status_code == 200
    body = r.json()
    items = body["items"] if isinstance(body, dict) else body
    assert {i["id"] for i in items} == {str(w["mine"])}


@pytest.mark.parametrize("who", ["owner", "manager"])
def test_given_an_owner_or_manager_when_managing_fields_then_accepted(client, token_for, world, who):
    w = world
    f = f"/v1/farms/{w['farm']}"
    r = req(client, token_for, w[who], "POST", f"{f}/fields", {"name": "New", "geometry": square(-7.7)})
    assert r.status_code == 201, r.text
    listed = req(client, token_for, w[who], "GET", f"{f}/fields").json()
    items = listed["items"] if isinstance(listed, dict) else listed
    assert {str(w["mine"]), str(w["other"])} <= {i["id"] for i in items}
    assert req(client, token_for, w[who], "GET", f"{f}/fields/archived").status_code == 200
    assert req(client, token_for, w[who], "POST", f"{f}/crops", {"name": "Safran", "cycle": "annual"}).status_code == 201


def test_given_a_token_issued_before_a_role_change_when_calling_then_the_role_is_read_from_the_database(client, token_for, world):
    w = world
    token = token_for(w["manager"])
    path = f"/v1/farms/{w['farm']}/fields"
    body = {"name": "New", "geometry": square(-7.7)}
    assert client.post(path, headers=auth(token), json=body).status_code == 201
    sql("UPDATE farm_members SET role='worker' WHERE user_id=$1", w["manager"])
    assert client.post(path, headers=auth(token), json={**body, "name": "Again"}).status_code in (403, 404)
    sql("UPDATE farm_members SET role='manager' WHERE user_id=$1", w["manager"])
    assert client.post(path, headers=auth(token), json={**body, "name": "Third"}).status_code == 201
