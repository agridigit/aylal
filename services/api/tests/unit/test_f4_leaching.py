"""T016 - leaching fraction (FAO-29) and gross need: Python mirrors the TS rules on the SAME shared vectors (f4_leaching.json)."""
import pytest

from tests.unit._f4 import run, vector_params


@pytest.mark.parametrize("v", vector_params("f4_leaching.json"))
def test_given_a_shared_vector_when_applying_the_rule_then_python_matches_the_ts_expectation(v):
    run(v, "app.domain.leaching")
