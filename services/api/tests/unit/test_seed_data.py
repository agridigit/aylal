"""T056 - deterministic seed data (trial account, 1 farm, 50 parcels)."""
from app.db.seed import build_seed


def test_given_the_seed_when_built_twice_then_it_is_identical() -> None:
    assert build_seed() == build_seed()


def test_given_the_seed_when_built_then_one_farm_and_fifty_parcels_with_unique_ids() -> None:
    seed = build_seed()
    assert len(seed.parcels) == 50
    assert len({p.id for p in seed.parcels}) == 50
    assert all(p.farm_id == seed.farm_id for p in seed.parcels)


def test_given_the_seed_when_built_then_the_trial_account_owns_the_farm() -> None:
    seed = build_seed()
    assert seed.members == {seed.user_id: "owner"}
