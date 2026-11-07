"""T035 - crop reference and free crops (R2-A1 to R2-A3)."""
import pytest

from tests.helpers import auth, sql
from tests.integration._f2 import add_custom_crop, new_user

SLUGS = ["olive", "citrus", "durum-wheat", "soft-wheat", "barley", "tomato", "potato", "onion", "berries", "avocado",
         "date-palm", "almond", "grape", "sugar-beet", "alfalfa", "silage-maize"]


@pytest.fixture
def world(make_farm, token_for):
    owner, worker, outsider = new_user(), new_user(), new_user()
    farm_a, farm_b = make_farm({owner: "owner", worker: "worker"}), make_farm({new_user(): "owner"})
    return dict(farm=farm_a, farm_b=farm_b, owner=auth(token_for(owner)), worker=auth(token_for(worker)), outsider=auth(token_for(outsider)))


def test_given_the_crop_list_when_it_loads_then_the_16_launch_crops_appear_each_with_a_photo(client, world):
    items = client.get("/v1/crops", headers=world["owner"]).json()["items"]
    ref = {c["slug"]: c for c in items if c["farm_id"] is None}
    assert sorted(ref) == sorted(SLUGS)
    assert all(c["photo_key"] and c["photo_key"].endswith(".webp") for c in ref.values())
    assert all(c["name_fr"] and c["name_ar"] and c["name_ary"] for c in ref.values())


def test_given_the_seeded_reference_when_reading_stages_then_they_are_marked_not_validated(client, world):
    ref = [c for c in client.get("/v1/crops", headers=world["owner"]).json()["items"] if c["farm_id"] is None]
    assert all(c["validated"] is False for c in ref) and all(c["stages"] for c in ref)


def test_given_a_missing_crop_when_the_owner_adds_a_free_crop_then_201_private_to_the_farm_without_agronomy(client, world):
    r = client.post(f"/v1/farms/{world['farm']}/crops", json={"name": "Safran", "cycle": "annual"}, headers=world["owner"])
    assert r.status_code == 201, r.text
    assert r.json()["farm_id"] == str(world["farm"]) and r.json()["has_agronomy"] is False
    mine = client.get(f"/v1/crops?farm_id={world['farm']}", headers=world["owner"]).json()["items"]
    assert "Safran" in [c["name_fr"] for c in mine]


def test_given_a_free_crop_of_farm_A_when_farm_B_lists_crops_then_it_is_invisible(client, world, token_for):
    cid = add_custom_crop(world["farm"])
    other = sql("SELECT user_id FROM farm_members WHERE farm_id=$1", world["farm_b"])[0][0]
    listed = client.get(f"/v1/crops?farm_id={world['farm_b']}", headers=auth(token_for(other))).json()["items"]
    assert str(cid) not in [c["id"] for c in listed]


def test_given_a_worker_when_adding_a_free_crop_then_403(client, world):
    assert client.post(f"/v1/farms/{world['farm']}/crops", json={"name": "X", "cycle": "annual"}, headers=world["worker"]).status_code == 403


def test_given_a_non_member_when_adding_or_listing_crops_of_a_farm_then_404(client, world):
    assert client.post(f"/v1/farms/{world['farm']}/crops", json={"name": "X", "cycle": "annual"}, headers=world["outsider"]).status_code == 404
    assert client.get(f"/v1/crops?farm_id={world['farm']}", headers=world["outsider"]).status_code == 404


@pytest.mark.parametrize("body", [{"name": "", "cycle": "annual"}, {"name": "x" * 81, "cycle": "annual"}, {"name": "X", "cycle": "weekly"}, {"cycle": "annual"}])
def test_given_an_invalid_free_crop_when_adding_then_422(client, world, body):
    assert client.post(f"/v1/farms/{world['farm']}/crops", json=body, headers=world["owner"]).status_code == 422
