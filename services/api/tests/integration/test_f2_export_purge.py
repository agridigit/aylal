"""T062 - personal-data export includes F2 data: managers all fields, a worker only the assigned ones."""
import asyncio

from app.accounts.export import build_export
from app.db.session import sessionmaker
from tests.integration._f2 import add_block, add_custom_crop, add_field, add_season, assign, new_user


def export_of(user):
    async def _run():
        async with sessionmaker() as session:
            return await build_export(session, user)

    return asyncio.run(_run())


def test_given_owner_and_worker_when_exporting_then_fields_seasons_blocks_follow_the_role(make_farm):
    owner, worker = new_user(), new_user()
    farm = make_farm({owner: "owner", worker: "worker"})
    mine, other = add_field(farm, "Mine"), add_field(farm, "Other")
    assign(farm, worker, mine)
    crop = add_custom_crop(farm)
    for f in (mine, other):
        add_season(farm, f, crop)
        add_block(farm, f)

    full = export_of(owner)
    assert {f["id"] for f in full["fields"]} == {str(mine), str(other)}
    assert len(full["seasons"]) == 2 and len(full["blocks"]) == 2
    assert [c["id"] for c in full["crops"]] == [str(crop)]

    part = export_of(worker)
    assert [f["id"] for f in part["fields"]] == [str(mine)]
    assert {s["field_id"] for s in part["seasons"]} == {str(mine)}
    assert {b["field_id"] for b in part["blocks"]} == {str(mine)}
