"""T005 - F2 cross-farm access is a 404 identical to an unknown farm, never 403 (guardrails 1 and 4)."""
import uuid

import pytest

from tests.helpers import auth, sql
from tests.integration._f2 import (
    add_block, add_custom_crop, add_field, add_season, new_user, reference_crop, square,
)


@pytest.fixture
def world(make_farm):
    owner_a, owner_b = new_user(), new_user()
    farm_a, farm_b = make_farm({owner_a: "owner"}), make_farm({owner_b: "owner"})
    field_a, field_b = add_field(farm_a, "A"), add_field(farm_b, "B", lon=-7.50)
    crop_b = add_custom_crop(farm_b)
    return dict(
        owner_a=owner_a, owner_b=owner_b, farm_a=farm_a, farm_b=farm_b, field_a=field_a, field_b=field_b,
        block_a=add_block(farm_a, field_a), block_b=add_block(farm_b, field_b),
        season_a=add_season(farm_a, field_a), season_b=add_season(farm_b, field_b, crop_b),
        crop_a=add_custom_crop(farm_a), crop_b=crop_b,
    )


def routes(farm, field, block, season):
    """Every F2 route as (method, path, json body) addressed on `farm` with the given child ids."""
    f = f"/v1/farms/{farm}"
    new_field = {"name": "N", "geometry": square(-7.7)}
    return [
        ("GET", f"{f}/fields", None),
        ("POST", f"{f}/fields", new_field),
        ("GET", f"{f}/fields/archived", None),
        ("GET", f"{f}/fields/{field}", None),
        ("PATCH", f"{f}/fields/{field}", {"name": "Renamed"}),
        ("DELETE", f"{f}/fields/{field}", None),
        ("POST", f"{f}/fields/{field}/restore", None),
        ("POST", f"{f}/fields/merge", {"survivor_id": str(field), "merged_ids": [str(uuid.uuid4())]}),
        ("GET", f"{f}/fields/{field}/blocks", None),
        ("POST", f"{f}/fields/{field}/blocks", {"name": "b", "kind": "block", "geometry": square(-7.6, 33.57, 0.0005)}),
        ("PATCH", f"{f}/fields/{field}/blocks/{block}", {"name": "b2"}),
        ("DELETE", f"{f}/fields/{field}/blocks/{block}", None),
        ("GET", f"{f}/fields/{field}/seasons", None),
        ("POST", f"{f}/fields/{field}/seasons", {"crop_id": str(reference_crop()), "started_at": "2026-01-01"}),
        ("GET", f"{f}/fields/{field}/seasons/{season}", None),
        ("PATCH", f"{f}/fields/{field}/seasons/{season}", {"stage_corrected": "flowering"}),
        ("GET", f"{f}/crops", None),
        ("POST", f"{f}/crops", {"name": "Safran", "cycle": "annual"}),
        ("GET", f"/v1/crops?farm_id={farm}", None),
    ]


def call(client, token, method, path, body):
    return client.request(method, path, headers=auth(token), json=body)


def signature(r):
    return r.status_code, r.content, {k: v for k, v in r.headers.items() if k not in ("date", "x-request-id", "content-length")}


def test_given_the_routes_exist_when_the_owner_calls_them_on_their_own_farm_then_none_is_missing_or_forbidden(client, token_for, world):
    w = world
    for method, path, body in routes(w["farm_a"], w["field_a"], w["block_a"], w["season_a"]):
        if method == "DELETE" or path.endswith(("/restore", "/merge")):
            continue  # destructive or state-dependent: covered by the other tests
        r = call(client, token_for(w["owner_a"]), method, path, body)
        assert r.status_code not in (403, 404, 405), f"{method} {path} -> {r.status_code}: route not implemented"


def test_given_a_non_member_when_calling_any_f2_route_then_404_identical_to_an_unknown_farm(client, token_for, world):
    w = world
    ghost = uuid.uuid4()
    for (m, p_real, b), (_, p_ghost, _) in zip(
        routes(w["farm_b"], w["field_b"], w["block_b"], w["season_b"]),
        routes(ghost, w["field_b"], w["block_b"], w["season_b"]),
    ):
        real = call(client, token_for(w["owner_a"]), m, p_real, b)
        unknown = call(client, token_for(w["owner_a"]), m, p_ghost, b)
        assert real.status_code == 404 != 403, f"{m} {p_real}"
        assert real.status_code == unknown.status_code
        assert real.content == unknown.content, f"{m} {p_real}: body differs from unknown farm"
        assert {k: v for k, v in real.headers.items() if k not in ("date", "content-length")} == {
            k: v for k, v in unknown.headers.items() if k not in ("date", "content-length")
        }
    assert sql("SELECT name FROM parcels WHERE id=$1", w["field_b"])[0][0] == "B"


def test_given_objects_of_another_farm_when_addressed_through_my_farm_then_404(client, token_for, world):
    w = world
    t = token_for(w["owner_a"])
    f = f"/v1/farms/{w['farm_a']}"
    cross = [
        ("GET", f"{f}/fields/{w['field_b']}", None),
        ("PATCH", f"{f}/fields/{w['field_b']}", {"name": "Hacked"}),
        ("DELETE", f"{f}/fields/{w['field_b']}", None),
        ("POST", f"{f}/fields/{w['field_b']}/restore", None),
        ("GET", f"{f}/fields/{w['field_b']}/blocks", None),
        ("PATCH", f"{f}/fields/{w['field_a']}/blocks/{w['block_b']}", {"name": "Hacked"}),
        ("DELETE", f"{f}/fields/{w['field_a']}/blocks/{w['block_b']}", None),
        ("GET", f"{f}/fields/{w['field_b']}/seasons", None),
        ("GET", f"{f}/fields/{w['field_a']}/seasons/{w['season_b']}", None),
        ("PATCH", f"{f}/fields/{w['field_a']}/seasons/{w['season_b']}", {"stage_corrected": "x"}),
    ]
    for m, p, b in cross:
        assert call(client, t, m, p, b).status_code == 404, f"{m} {p}"
    assert sql("SELECT count(*) FROM parcels WHERE id=$1 AND name='B' AND archived_at IS NULL", w["field_b"])[0][0] == 1
    assert sql("SELECT count(*) FROM field_blocks WHERE id=$1 AND name='Block'", w["block_b"])[0][0] == 1


def test_given_a_crop_of_another_farm_when_starting_a_season_then_404_and_nothing_is_written(client, token_for, world):
    w = world
    r = call(client, token_for(w["owner_a"]), "POST", f"/v1/farms/{w['farm_a']}/fields/{w['field_a']}/seasons",
             {"crop_id": str(w["crop_b"]), "started_at": "2026-01-01"})
    assert r.status_code == 404
    assert sql("SELECT count(*) FROM seasons WHERE field_id=$1", w["field_a"])[0][0] == 1  # only the seeded one
    ok = call(client, token_for(w["owner_a"]), "POST", f"/v1/farms/{w['farm_a']}/fields/{w['field_a']}/seasons",
              {"crop_id": str(w["crop_a"]), "started_at": "2026-01-01"})
    assert ok.status_code != 404, "own free crop must be found"


def test_given_fields_of_another_farm_when_merging_then_404_and_nothing_changes(client, token_for, world):
    w = world
    mine = add_field(w["farm_a"], "A2", lon=-7.61)
    t = token_for(w["owner_a"])
    f = f"/v1/farms/{w['farm_a']}/fields/merge"
    for body in (
        {"survivor_id": str(w["field_b"]), "merged_ids": [str(w["field_a"])]},
        {"survivor_id": str(w["field_a"]), "merged_ids": [str(w["field_b"])]},
        {"survivor_id": str(w["field_a"]), "merged_ids": [str(mine), str(w["field_b"])]},
    ):
        assert call(client, t, "POST", f, body).status_code == 404
    assert sql("SELECT count(*) FROM parcels WHERE archived_at IS NOT NULL")[0][0] == 0


def test_given_a_deleted_farm_when_its_owner_calls_any_f2_route_then_404(client, token_for, world):
    w = world
    sql("UPDATE farms SET deleted_at = now() WHERE id=$1", w["farm_a"])
    ghost = uuid.uuid4()
    for (m, p, b), (_, pg, _) in zip(
        routes(w["farm_a"], w["field_a"], w["block_a"], w["season_a"]),
        routes(ghost, w["field_a"], w["block_a"], w["season_a"]),
    ):
        r = call(client, token_for(w["owner_a"]), m, p, b)
        g = call(client, token_for(w["owner_a"]), m, pg, b)
        assert r.status_code == 404 and r.content == g.content, f"{m} {p}"
