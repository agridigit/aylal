"""T014 - shared TS/Python vectors f8_economics.json: the Python mirror gives the same answers as the TS rule."""
import pytest

from tests.unit._f8 import run, vector_params


@pytest.mark.parametrize("v", vector_params("f8_economics.json"))
def test_given_a_shared_vector_when_applying_the_python_mirror_then_it_matches_the_ts_expectation(v):
    run(v, "app.domain.farm_economics")


def test_given_random_lines_when_computing_then_margin_is_exactly_revenue_minus_expenses():
    import random

    from app.domain.farm_economics import parcel_economics

    rnd = random.Random(11)
    for _ in range(200):
        exp = [rnd.randint(-500_000, 1_500_000) for _ in range(rnd.randint(0, 8))]
        sal = [rnd.randint(0, 2_000_000) for _ in range(rnd.randint(0, 8))]
        out = parcel_economics({"expense_lines_cents": exp, "sale_lines_cents": sal, "harvested_milli": rnd.randint(0, 2) * 100000, "area_m2": rnd.randint(1000, 50000)})
        assert out["expenses_cents"] == sum(exp) and out["revenue_cents"] == sum(sal)
        assert out["margin_cents"] == out["revenue_cents"] - out["expenses_cents"]
