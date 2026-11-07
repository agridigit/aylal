"""T035 - initial campaign, optional variety, cycle dates and kept stage correction (R2-A1, R2-A3 to R2-A5)."""
import pytest

from tests.helpers import auth, sql
from tests.integration._f2 import add_custom_crop, add_field, new_user


@pytest.fixture
def world(make_farm, token_for):
    owner = new_user()
    farm = make_farm({owner: "owner"})
    field = add_field(farm, "A")
    crops = {r["slug"]: r["id"] for r in sql("SELECT id, slug FROM crops WHERE farm_id IS NULL")}
    return dict(farm=farm, field=field, h=auth(token_for(owner)), crops=crops, base=f"/v1/farms/{farm}/fields/{field}/seasons")


def test_given_a_crop_without_knowing_the_variety_when_starting_the_campaign_then_201_with_a_null_variety(client, world):
    r = client.post(world["base"], json={"crop_id": str(world["crops"]["durum-wheat"]), "sowing_date": "2026-01-10", "started_at": "2026-01-10"}, headers=world["h"])
    assert r.status_code == 201, r.text
    assert r.json()["variety"] is None


def test_given_a_known_variety_when_starting_the_campaign_then_it_is_stored(client, world):
    r = client.post(world["base"], json={"crop_id": str(world["crops"]["olive"]), "variety": "Picholine", "planting_year": 2015, "started_at": "2026-01-01"}, headers=world["h"])
    assert r.status_code == 201 and r.json()["variety"] == "Picholine"


@pytest.mark.parametrize(("slug", "body"), [
    ("olive", {"sowing_date": "2026-01-10"}),                                   # perennial needs a planting year
    ("durum-wheat", {"planting_year": 2020}),                                   # annual needs a sowing date
    ("olive", {"planting_year": 2015, "sowing_date": "2026-01-10"}),            # never both
    ("durum-wheat", {"planting_year": 2020, "sowing_date": "2026-01-10"}),
    ("olive", {"planting_year": 2999}),                                         # future year
])
def test_given_dates_inconsistent_with_the_crop_cycle_when_starting_then_422(client, world, slug, body):
    r = client.post(world["base"], json={"crop_id": str(world["crops"][slug]), "started_at": "2026-01-10", **body}, headers=world["h"])
    assert r.status_code == 422


def test_given_a_free_crop_when_starting_a_campaign_then_it_is_usable_on_the_field(client, world):
    cid = add_custom_crop(world["farm"])
    r = client.post(world["base"], json={"crop_id": str(cid), "sowing_date": "2026-02-01", "started_at": "2026-02-01"}, headers=world["h"])
    assert r.status_code == 201


def test_given_a_campaign_with_a_sowing_date_when_it_is_created_then_the_stage_is_estimated_automatically(client, world):
    r = client.post(world["base"], json={"crop_id": str(world["crops"]["durum-wheat"]), "sowing_date": "2026-01-01", "started_at": "2026-01-01"}, headers=world["h"])
    assert r.status_code == 201 and r.json()["stage_estimated"]


def test_given_a_free_crop_campaign_then_no_stage_is_estimated(client, world):
    cid = add_custom_crop(world["farm"])
    r = client.post(world["base"], json={"crop_id": str(cid), "sowing_date": "2026-02-01", "started_at": "2026-02-01"}, headers=world["h"])
    assert r.json()["stage_estimated"] is None


def test_given_an_estimated_stage_when_the_farmer_corrects_it_then_the_correction_is_kept_and_shown_first(client, world):
    sid = client.post(world["base"], json={"crop_id": str(world["crops"]["durum-wheat"]), "sowing_date": "2026-01-01", "started_at": "2026-01-01"}, headers=world["h"]).json()["id"]
    r = client.patch(f"{world['base']}/{sid}", json={"stage_corrected": "heading"}, headers=world["h"])
    assert r.status_code == 200 and r.json()["stage_corrected"] == "heading" and r.json()["stage_corrected_at"]
    again = client.get(f"{world['base']}/{sid}", headers=world["h"]).json()
    assert again["stage_corrected"] == "heading"


def test_given_a_corrected_stage_when_the_estimate_is_refreshed_then_the_correction_survives(client, world):
    sid = client.post(world["base"], json={"crop_id": str(world["crops"]["durum-wheat"]), "sowing_date": "2026-01-01", "started_at": "2026-01-01"}, headers=world["h"]).json()["id"]
    client.patch(f"{world['base']}/{sid}", json={"stage_corrected": "heading"}, headers=world["h"])
    client.patch(f"{world['base']}/{sid}", json={"variety": "Karim"}, headers=world["h"])
    got = client.get(f"{world['base']}/{sid}", headers=world["h"]).json()
    assert got["stage_corrected"] == "heading" and got["variety"] == "Karim"


def test_given_a_crop_of_another_farm_when_starting_a_campaign_then_404(client, world, make_farm):
    foreign = add_custom_crop(make_farm({new_user(): "owner"}))
    r = client.post(world["base"], json={"crop_id": str(foreign), "sowing_date": "2026-02-01", "started_at": "2026-02-01"}, headers=world["h"])
    assert r.status_code == 404
