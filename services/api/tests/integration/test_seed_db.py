"""T056 - seed written to the real database is complete and idempotent."""
import asyncio

from tests.helpers import sql


def _run_seed():
    from app.db.seed import seed
    from app.db.session import sessionmaker

    async def _go():
        async with sessionmaker() as session:
            return await seed(session)

    return asyncio.run(_go())


def test_given_an_empty_database_when_seeding_twice_then_one_farm_and_fifty_parcels_exist(clean_db) -> None:
    first = _run_seed()
    second = _run_seed()
    assert first == second
    assert sql("SELECT count(*) AS n FROM farms WHERE id = $1", first.farm_id)[0]["n"] == 1
    assert sql("SELECT count(*) AS n FROM parcels WHERE farm_id = $1", first.farm_id)[0]["n"] == 50
    role = sql("SELECT role FROM farm_members WHERE farm_id = $1 AND user_id = $2", first.farm_id, first.user_id)
    assert role[0]["role"] == "owner"
