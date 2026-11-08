"""T014 - shared TS/Python vectors f8_stock.json: the Python mirror gives the same answers as the TS rule."""
import pytest

from tests.unit._f8 import run, vector_params


@pytest.mark.parametrize("v", vector_params("f8_stock.json"))
def test_given_a_shared_vector_when_applying_the_python_mirror_then_it_matches_the_ts_expectation(v):
    run(v, "app.domain.stock_ledger")
