"""T051 - complete field list for the map (R4-A1, R4-A2)."""
import pytest

from tests.helpers import auth, sql
from tests.integration._f2 import add_field, assign, new_user


@pytest.fixture
def world(make_farm, token_for):
    owner, worker = new_user(), new_user()
    farm = make_farm({owner: "owner", worker: "worker"})
    ids = [add_field(farm, f"F{i:02d}", lon=-7.9 + i * 0.003) for i in range(50)]
    return dict(farm=farm, ids=ids, owner=auth(token_for(owner)), worker=auth(token_for(worker)), worker_id=worker)


def test_given_a_farm_of_50_fields_when_the_owner_lists_them_then_all_50_come_with_geometry_and_status(client, world):
    r = client.get(f"/v1/farms/{world['farm']}/fields", headers=world["owner"])
    assert r.status_code == 200 and len(r.json()["items"]) == 50
    first = r.json()["items"][0]
    assert first["geometry"]["type"] == "Polygon" and "status_summary" in first and "area_calc_ha" in first


def test_given_a_field_whose_status_is_not_computed_when_listing_then_status_summary_is_null(client, world):
    sql("UPDATE parcels SET status_summary='act' WHERE id=$1", world["ids"][0])
    items = {f["id"]: f for f in client.get(f"/v1/farms/{world['farm']}/fields", headers=world["owner"]).json()["items"]}
    assert items[str(world["ids"][0])]["status_summary"] == "act"
    assert items[str(world["ids"][1])]["status_summary"] is None


def test_given_a_worker_assigned_to_three_fields_when_listing_then_only_those_three_appear(client, world):
    for fid in world["ids"][:3]:
        assign(world["farm"], world["worker_id"], fid)
    items = client.get(f"/v1/farms/{world['farm']}/fields", headers=world["worker"]).json()["items"]
    assert sorted(f["id"] for f in items) == sorted(str(i) for i in world["ids"][:3])


def test_given_an_archived_field_when_listing_then_it_is_absent_and_its_card_is_404(client, world):
    sql("UPDATE parcels SET archived_at=now() WHERE id=$1", world["ids"][0])
    ids = [f["id"] for f in client.get(f"/v1/farms/{world['farm']}/fields", headers=world["owner"]).json()["items"]]
    assert str(world["ids"][0]) not in ids and len(ids) == 49
    assert client.get(f"/v1/farms/{world['farm']}/fields/{world['ids'][0]}", headers=world["owner"]).status_code == 404


def test_given_a_deleted_farm_when_listing_then_404(client, world):
    sql("UPDATE farms SET deleted_at=now() WHERE id=$1", world["farm"])
    assert client.get(f"/v1/farms/{world['farm']}/fields", headers=world["owner"]).status_code == 404


def test_given_a_field_card_when_opened_from_the_map_then_it_returns_the_same_data_as_the_list(client, world):
    listed = client.get(f"/v1/farms/{world['farm']}/fields", headers=world["owner"]).json()["items"][0]
    card = client.get(f"/v1/farms/{world['farm']}/fields/{listed['id']}", headers=world["owner"])
    assert card.status_code == 200 and card.json()["name"] == listed["name"]

