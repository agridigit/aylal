"""T066 - rotation, double-campaign block, intercropping, history, guard-rails (R6-A1 to R6-A3)."""
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest

from tests.helpers import auth, sql
from tests.integration._f2 import add_field, assign, new_user


@pytest.fixture
def w(make_farm, token_for):
    owner, worker, stranger = new_user(), new_user(), new_user()
    farm = make_farm({owner: "owner", worker: "worker"})
    other = make_farm({stranger: "owner"})
    field, other_field = add_field(farm, "A"), add_field(farm, "B", lon=-7.5)
    assign(farm, worker, field)
    crops = {r["slug"]: r["id"] for r in sql("SELECT id, slug FROM crops WHERE farm_id IS NULL")}
    return dict(farm=farm, other=other, field=field, other_field=other_field, foreign=add_field(other, "X"), crops=crops,
                h=auth(token_for(owner)), hw=auth(token_for(worker)), hs=auth(token_for(stranger)))


def base(w, field=None, farm=None):
    return f"/v1/farms/{farm or w['farm']}/fields/{field or w['field']}/seasons"


def wheat(w, started="2026-01-10", **extra):
    return {"crop_id": str(w["crops"]["durum-wheat"]), "sowing_date": started, "started_at": started, **extra}


def olive(w, started="2026-03-01", **extra):
    return {"crop_id": str(w["crops"]["olive"]), "planting_year": 2015, "started_at": started, **extra}


def test_given_an_active_campaign_when_starting_another_crop_with_close_ids_then_the_previous_is_closed_and_still_consultable(client, w):
    first = client.post(base(w), json=wheat(w), headers=w["h"]).json()
    r = client.post(base(w), json=olive(w, close_ids=[first["id"]]), headers=w["h"])
    assert r.status_code == 201, r.text
    old = client.get(f"{base(w)}/{first['id']}", headers=w["h"])
    assert old.status_code == 200 and old.json()["ended_at"] == "2026-03-01"
    items = client.get(base(w), headers=w["h"]).json()["items"]
    assert {s["id"] for s in items} == {first["id"], r.json()["id"]}
    assert [s["ended_at"] is None for s in items if s["id"] == r.json()["id"]] == [True]


def test_given_an_active_crop_when_starting_the_same_crop_again_then_409_season_already_active_and_nothing_is_written(client, w):
    assert client.post(base(w), json=wheat(w), headers=w["h"]).status_code == 201
    r = client.post(base(w), json=wheat(w, "2026-02-01"), headers=w["h"])
    assert r.status_code == 409 and "season_already_active" in r.text
    assert sql("SELECT count(*) FROM seasons WHERE field_id=$1", w["field"])[0][0] == 1


def test_given_a_refused_duplicate_with_close_ids_for_another_season_then_that_season_is_not_closed(client, w):
    wid = client.post(base(w), json=wheat(w), headers=w["h"]).json()["id"]
    oid = client.post(base(w), json=olive(w), headers=w["h"]).json()["id"]
    r = client.post(base(w), json=wheat(w, "2026-04-01", close_ids=[oid]), headers=w["h"])
    assert r.status_code == 409
    assert sql("SELECT ended_at FROM seasons WHERE id=$1", uuid.UUID(oid))[0][0] is None  # atomic: the close rolled back
    assert sql("SELECT ended_at FROM seasons WHERE id=$1", uuid.UUID(wid))[0][0] is None


def test_given_an_active_crop_when_closing_and_restarting_the_same_crop_in_one_request_then_201(client, w):
    first = client.post(base(w), json=wheat(w), headers=w["h"]).json()
    r = client.post(base(w), json=wheat(w, "2026-09-01", close_ids=[first["id"]]), headers=w["h"])
    assert r.status_code == 201


def test_given_intercropped_crops_when_adding_a_different_crop_without_close_ids_then_both_are_active(client, w):
    assert client.post(base(w), json=olive(w), headers=w["h"]).status_code == 201
    assert client.post(base(w), json=wheat(w), headers=w["h"]).status_code == 201
    assert sql("SELECT count(*) FROM seasons WHERE field_id=$1 AND ended_at IS NULL", w["field"])[0][0] == 2


def test_given_close_ids_of_a_season_on_another_field_or_farm_when_starting_then_that_season_stays_active(client, w):
    mine = client.post(base(w, w["other_field"]), json=wheat(w), headers=w["h"]).json()["id"]
    sql("INSERT INTO seasons (id, farm_id, field_id, crop_id, started_at) VALUES ($1,$2,$3,$4,current_date)", uuid.UUID(int=7), w["other"], w["foreign"], w["crops"]["olive"])
    r = client.post(base(w), json=olive(w, close_ids=[mine, str(uuid.UUID(int=7))]), headers=w["h"])
    assert r.status_code in (201, 404)
    assert sql("SELECT count(*) FROM seasons WHERE ended_at IS NOT NULL")[0][0] == 0


def test_given_a_season_when_closing_it_by_patch_then_it_is_kept_and_a_closed_crop_can_be_started_again(client, w):
    sid = client.post(base(w), json=wheat(w), headers=w["h"]).json()["id"]
    r = client.patch(f"{base(w)}/{sid}", json={"ended_at": "2026-06-30"}, headers=w["h"])
    assert r.status_code == 200 and r.json()["ended_at"] == "2026-06-30"
    assert client.post(base(w), json=wheat(w, "2026-10-01"), headers=w["h"]).status_code == 201


def test_given_a_closed_and_an_active_season_of_the_same_crop_when_reopening_the_closed_one_then_409_not_500(client, w):
    sid = client.post(base(w), json=wheat(w), headers=w["h"]).json()["id"]
    client.patch(f"{base(w)}/{sid}", json={"ended_at": "2026-06-30"}, headers=w["h"])
    assert client.post(base(w), json=wheat(w, "2026-10-01"), headers=w["h"]).status_code == 201
    r = client.patch(f"{base(w)}/{sid}", json={"ended_at": None}, headers=w["h"])
    assert r.status_code == 409


def test_given_a_worker_when_starting_or_closing_a_campaign_then_403(client, w):
    sid = client.post(base(w), json=wheat(w), headers=w["h"]).json()["id"]
    assert client.post(base(w), json=olive(w), headers=w["hw"]).status_code == 403
    assert client.patch(f"{base(w)}/{sid}", json={"ended_at": "2026-06-30"}, headers=w["hw"]).status_code == 403
    assert sql("SELECT ended_at FROM seasons WHERE id=$1", uuid.UUID(sid))[0][0] is None


def test_given_a_season_of_another_field_or_farm_when_reading_or_closing_it_through_this_field_then_404(client, w):
    sid = client.post(base(w, w["other_field"]), json=wheat(w), headers=w["h"]).json()["id"]
    assert client.get(f"{base(w)}/{sid}", headers=w["h"]).status_code == 404
    assert client.patch(f"{base(w)}/{sid}", json={"ended_at": "2026-06-30"}, headers=w["h"]).status_code == 404
    assert client.get(f"{base(w, w['foreign'])}/{sid}", headers=w["h"]).status_code == 404
    ghost = client.get(f"{base(w, farm=uuid.uuid4())}/{sid}", headers=w["hs"])
    mine = client.get(f"{base(w)}/{sid}", headers=w["hs"])
    assert ghost.status_code == mine.status_code == 404 and ghost.content == mine.content


def test_given_a_closing_date_before_the_start_when_patching_then_422(client, w):
    sid = client.post(base(w), json=wheat(w), headers=w["h"]).json()["id"]
    assert client.patch(f"{base(w)}/{sid}", json={"ended_at": "2025-01-01"}, headers=w["h"]).status_code == 422


def test_given_parallel_starts_of_the_same_crop_when_racing_then_exactly_one_wins_and_the_others_get_409(client, w):
    def start(i):
        return client.post(base(w), json=wheat(w, f"2026-01-{10 + i}"), headers=w["h"]).status_code

    with ThreadPoolExecutor(8) as pool:
        codes = list(pool.map(start, range(8)))
    assert sorted(codes) == [201] + [409] * 7, codes
    assert sql("SELECT count(*) FROM seasons WHERE field_id=$1 AND ended_at IS NULL", w["field"])[0][0] == 1
