"""T058 - split a field into blocks / irrigation sectors (R5-A1) with guard-rails 1, 2 and 4."""
import uuid

import pytest

from tests.helpers import auth, sql
from tests.integration._f2 import add_block, add_field, assign, new_user, square

INSIDE = square(-7.60, 33.57, 0.0009)
OTHER_INSIDE = square(-7.5989, 33.5711, 0.0008)  # field is 0.002 wide: disjoint from INSIDE


@pytest.fixture
def w(make_farm, token_for):
    owner, manager, worker, stranger = new_user(), new_user(), new_user(), new_user()
    farm = make_farm({owner: "owner", manager: "manager", worker: "worker"})
    other_farm = make_farm({stranger: "owner"})
    field, other_field = add_field(farm, "A"), add_field(farm, "B", lon=-7.5)
    assign(farm, worker, field)
    return dict(farm=farm, other_farm=other_farm, field=field, other_field=other_field, foreign=add_field(other_farm, "X"),
                owner=auth(token_for(owner)), manager=auth(token_for(manager)), worker=auth(token_for(worker)), stranger=auth(token_for(stranger)))


def url(w, field=None, block=None, farm=None):
    u = f"/v1/farms/{farm or w['farm']}/fields/{field or w['field']}/blocks"
    return u + (f"/{block}" if block else "")


def test_given_a_field_when_splitting_it_into_two_blocks_then_each_has_its_geometry_and_area_attached_to_the_field(client, w):
    a = client.post(url(w), json={"name": "N", "kind": "block", "geometry": INSIDE}, headers=w["owner"])
    b = client.post(url(w), json={"name": "S", "kind": "irrigation_sector", "geometry": OTHER_INSIDE}, headers=w["manager"])
    assert a.status_code == 201 and b.status_code == 201, (a.text, b.text)
    assert a.json()["field_id"] == str(w["field"]) and a.json()["area_calc_ha"] > 0 and b.json()["kind"] == "irrigation_sector"
    listed = client.get(url(w), headers=w["owner"]).json()["items"]
    assert {x["name"] for x in listed} == {"N", "S"}
    assert sql("SELECT count(*) FROM parcels WHERE farm_id=$1 AND archived_at IS NULL", w["farm"])[0][0] == 2  # the field stays, no new field


def test_given_a_block_outside_the_field_when_splitting_then_422_block_outside_field_and_nothing_is_written(client, w):
    r = client.post(url(w), json={"name": "Out", "kind": "block", "geometry": square(-7.5, 33.57, 0.0005)}, headers=w["owner"])
    assert r.status_code == 422 and "block_outside_field" in r.text
    assert sql("SELECT count(*) FROM field_blocks WHERE field_id=$1", w["field"])[0][0] == 0


def test_given_a_block_overlapping_another_when_splitting_then_422_block_overlap(client, w):
    assert client.post(url(w), json={"name": "N", "kind": "block", "geometry": INSIDE}, headers=w["owner"]).status_code == 201
    r = client.post(url(w), json={"name": "Dup", "kind": "block", "geometry": square(-7.5997, 33.5703, 0.0006)}, headers=w["owner"])
    assert r.status_code == 422 and "block_overlap" in r.text


def test_given_a_block_overflowing_by_less_than_one_percent_when_splitting_then_it_is_accepted(client, w):
    nearly = square(-7.60 - 0.0000005, 33.57, 0.0009)
    assert client.post(url(w), json={"name": "Edge", "kind": "block", "geometry": nearly}, headers=w["owner"]).status_code == 201


def test_given_a_worker_assigned_to_the_field_when_splitting_or_editing_then_403(client, w):
    bid = add_block(w["farm"], w["field"])
    for call in (
        lambda: client.post(url(w), json={"name": "N", "kind": "block", "geometry": INSIDE}, headers=w["worker"]),
        lambda: client.patch(url(w, block=bid), json={"name": "Z"}, headers=w["worker"]),
        lambda: client.delete(url(w, block=bid), headers=w["worker"]),
    ):
        assert call().status_code == 403


def test_given_a_block_of_another_field_when_patching_or_deleting_it_through_this_field_then_404(client, w):
    foreign_block = add_block(w["farm"], w["other_field"])
    assert client.patch(url(w, block=foreign_block), json={"name": "Z"}, headers=w["owner"]).status_code == 404
    assert client.delete(url(w, block=foreign_block), headers=w["owner"]).status_code == 404
    assert sql("SELECT count(*) FROM field_blocks WHERE id=$1", foreign_block)[0][0] == 1


def test_given_another_farm_when_reaching_blocks_then_404_identical_to_an_unknown_farm(client, w):
    body = {"name": "N", "kind": "block", "geometry": INSIDE}
    ghost = client.post(url(w, farm=uuid.uuid4()), json=body, headers=w["stranger"])
    mine = client.post(url(w), json=body, headers=w["stranger"])
    assert ghost.status_code == mine.status_code == 404 and ghost.content == mine.content
    # a field of another farm addressed through the caller's own farm
    assert client.post(url(w, field=w["foreign"]), json=body, headers=w["owner"]).status_code == 404
    bid = add_block(w["other_farm"], w["foreign"])
    assert client.patch(url(w, field=w["foreign"], block=bid), json={"name": "Z"}, headers=w["owner"]).status_code == 404


def test_given_an_archived_field_when_splitting_or_listing_blocks_then_404(client, w):
    sql("UPDATE parcels SET archived_at=now(), purge_after=now()+interval '90 days' WHERE id=$1", w["field"])
    assert client.post(url(w), json={"name": "N", "kind": "block", "geometry": INSIDE}, headers=w["owner"]).status_code == 404
    assert client.get(url(w), headers=w["owner"]).status_code == 404


def test_given_a_block_when_patching_its_geometry_then_the_area_is_recomputed_and_the_inside_rule_applies(client, w):
    bid = client.post(url(w), json={"name": "N", "kind": "block", "geometry": INSIDE}, headers=w["owner"]).json()["id"]
    before = client.get(url(w), headers=w["owner"]).json()["items"][0]["area_calc_ha"]
    ok = client.patch(url(w, block=bid), json={"geometry": square(-7.60, 33.57, 0.0004)}, headers=w["owner"])
    assert ok.status_code == 200 and ok.json()["area_calc_ha"] < before
    bad = client.patch(url(w, block=bid), json={"geometry": square(-7.5, 33.57, 0.0004)}, headers=w["owner"])
    assert bad.status_code == 422 and "block_outside_field" in bad.text
