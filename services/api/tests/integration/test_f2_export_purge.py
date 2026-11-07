"""T062 - personal-data export includes F2 data: managers all fields, a worker only the assigned ones."""
from tests.helpers import auth
from tests.integration._f2 import add_block, add_custom_crop, add_field, add_season, assign, new_user


def test_given_owner_and_worker_when_exporting_then_fields_seasons_blocks_follow_the_role(client, token_for, make_farm):
    owner, worker = new_user(), new_user()
    farm = make_farm({owner: "owner", worker: "worker"})
    mine, other = add_field(farm, "Mine"), add_field(farm, "Other")
    assign(farm, worker, mine)
    crop = add_custom_crop(farm)
    for f in (mine, other):
        add_season(farm, f, crop)
        add_block(farm, f)

    full = client.get("/v1/me/export", headers=auth(token_for(owner))).json()
    assert {f["id"] for f in full["fields"]} == {str(mine), str(other)}
    assert len(full["seasons"]) == 2 and len(full["blocks"]) == 2
    assert [c["id"] for c in full["crops"]] == [str(crop)]

    part = client.get("/v1/me/export", headers=auth(token_for(worker))).json()
    assert [f["id"] for f in part["fields"]] == [str(mine)]
    assert {s["field_id"] for s in part["seasons"]} == {str(mine)}
    assert {b["field_id"] for b in part["blocks"]} == {str(mine)}
