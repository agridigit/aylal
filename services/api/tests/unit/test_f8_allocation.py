"""T014 - shared TS/Python vectors f8_allocation.json: the Python mirror gives the same answers as the TS rule."""
import pytest

from tests.unit._f8 import run, vector_params


@pytest.mark.parametrize("v", vector_params("f8_allocation.json"))
def test_given_a_shared_vector_when_applying_the_python_mirror_then_it_matches_the_ts_expectation(v):
    run(v, "app.domain.expense_allocation")


def test_given_random_amounts_and_surfaces_when_allocating_then_the_shares_sum_exactly_to_the_amount():
    import random

    from app.domain.expense_allocation import allocate

    rnd = random.Random(7)
    for _ in range(300):
        parcels = [{"id": f"p{j:02d}", "area_m2": rnd.randint(1, 90000)} for j in range(rnd.randint(1, 12))]
        amount = rnd.randint(1, 5_000_000)
        shares = allocate({"amount_cents": amount, "parcels": parcels})["shares"]
        assert sum(s["share_cents"] for s in shares) == amount and all(s["share_cents"] >= 0 for s in shares)


def test_given_the_same_input_in_any_order_then_each_parcel_gets_the_same_share():
    from app.domain.expense_allocation import allocate

    parcels = [{"id": "b", "area_m2": 4}, {"id": "a", "area_m2": 4}, {"id": "c", "area_m2": 4}]
    one = {s["id"]: s["share_cents"] for s in allocate({"amount_cents": 10001, "parcels": parcels})["shares"]}
    two = {s["id"]: s["share_cents"] for s in allocate({"amount_cents": 10001, "parcels": list(reversed(parcels))})["shares"]}
    assert one == two
