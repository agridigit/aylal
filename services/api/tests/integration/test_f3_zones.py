"""T062 - R4-A1..A3: zones are listed with their outline; an observation attached to a zone (REST or sync) moves it open -> visited.

Decision (specs/006-dashboard-monitoring/decisions.md): the data model says `open -> visited (observation recorded)`; the spec and CPS 8 are silent.
Only the server moves the status; a dismissed or resolved zone is never reopened by an observation.
"""
import uuid

import pytest

from tests.helpers import sql
from tests.integration._f3 import call, seed_zone, sync_obs, sync_post, world3  # noqa: F401

NOT_FOUND = {"detail": "not_found"}


def _status(z):
    return sql("SELECT status FROM attention_zones WHERE id = $1", z)[0][0]


def _rest_obs(client, token_for, w, z, who="worker", note="feuilles jaunes"):
    return call(client, token_for(w[who]), "POST", f"/v1/farms/{w['farm_a']}/zones/{z}/observations", {"id": str(uuid.uuid4()), "note": note})


def test_given_an_open_zone_when_a_worker_records_an_observation_by_rest_then_the_zone_becomes_visited(client, token_for, world3):
    w = world3
    z = seed_zone(w["farm_a"], w["a1"])
    assert _rest_obs(client, token_for, w, z).status_code == 201
    assert _status(z) == "visited"


def test_given_an_open_zone_when_an_observation_is_uploaded_by_sync_then_the_zone_becomes_visited(client, token_for, world3):
    w = world3
    z = seed_zone(w["farm_a"], w["a1"])
    r = sync_post(client, token_for(w["worker"]), [sync_obs(w["farm_a"], z)])
    assert r.status_code == 200 and r.json()["results"][0]["status"] == "applied", r.text
    assert _status(z) == "visited"


def test_given_an_observation_replayed_with_the_same_id_then_it_is_stored_once_and_the_zone_stays_visited(client, token_for, world3):
    w = world3
    z, rid = seed_zone(w["farm_a"], w["a1"]), uuid.uuid4()
    for _ in range(2):
        assert call(client, token_for(w["worker"]), "POST", f"/v1/farms/{w['farm_a']}/zones/{z}/observations", {"id": str(rid), "note": "x"}).status_code == 201
    assert sql("SELECT count(*) FROM zone_observations WHERE id = $1", rid)[0][0] == 1 and _status(z) == "visited"


@pytest.mark.parametrize("state", ["dismissed", "resolved"])
def test_given_a_dismissed_or_resolved_zone_when_an_observation_is_recorded_then_the_status_is_unchanged(client, token_for, world3, state):
    w = world3
    z = seed_zone(w["farm_a"], w["a1"], status=state)
    assert _rest_obs(client, token_for, w, z, who="manager").status_code == 201
    assert _status(z) == state


def test_given_a_rejected_observation_by_a_worker_on_a_hidden_parcel_then_the_zone_stays_open(client, token_for, world3):
    w = world3
    z = seed_zone(w["farm_a"], w["hidden"])
    assert _rest_obs(client, token_for, w, z).status_code == 404
    assert _status(z) == "open"


def test_given_an_observation_over_the_quota_when_recorded_then_429_and_the_zone_status_is_unchanged(client, token_for, world3):
    w = world3
    z = seed_zone(w["farm_a"], w["a1"])
    for _ in range(20):
        sql("INSERT INTO zone_observations (id, farm_id, zone_id, parcel_id, author_id, note) VALUES ($1,$2,$3,$4,$5,'q')", uuid.uuid4(), w["farm_a"], z, w["a1"], w["owner"])
    assert _rest_obs(client, token_for, w, z).status_code == 429
    assert _status(z) == "open"


def test_given_zones_when_listing_then_each_has_its_outline_centroid_status_and_visited_zones_stay_listed_for_guidance(client, token_for, world3):
    w = world3
    z_open, z_visited = seed_zone(w["farm_a"], w["a1"]), seed_zone(w["farm_a"], w["a1"], status="visited")
    got = {x["id"]: x for x in call(client, token_for(w["worker"]), "GET", f"/v1/farms/{w['farm_a']}/zones").json()}
    assert got[str(z_open)]["geometry"]["type"] == "Polygon" and got[str(z_open)]["centroid"]["type"] == "Point"
    assert got[str(z_visited)]["status"] == "visited"


def test_given_zones_on_hidden_parcels_when_a_worker_lists_then_none_is_served(client, token_for, world3):
    w = world3
    hidden = seed_zone(w["farm_a"], w["hidden"])
    assert str(hidden) not in {x["id"] for x in call(client, token_for(w["worker"]), "GET", f"/v1/farms/{w['farm_a']}/zones").json()}


def test_given_a_worker_when_dismissing_a_zone_then_403_and_the_zone_is_untouched(client, token_for, world3):
    w = world3
    z = seed_zone(w["farm_a"], w["a1"])
    assert call(client, token_for(w["worker"]), "POST", f"/v1/farms/{w['farm_a']}/zones/{z}/dismiss").status_code == 403
    assert _status(z) == "open"


def test_given_a_manager_when_dismissing_a_zone_then_it_is_dismissed(client, token_for, world3):
    w = world3
    z = seed_zone(w["farm_a"], w["a1"])
    r = call(client, token_for(w["manager"]), "POST", f"/v1/farms/{w['farm_a']}/zones/{z}/dismiss")
    assert r.status_code == 200 and r.json()["status"] == "dismissed" and _status(z) == "dismissed"


def test_given_a_zone_of_another_farm_when_observing_then_404_identical(client, token_for, world3):
    w = world3
    other = seed_zone(w["farm_b"], w["b1"])
    r = _rest_obs(client, token_for, w, other, who="owner")
    assert r.status_code == 404 and r.json() == NOT_FOUND
