"""T016 - advice rules: Python mirrors the shared vectors (rain postponement strictly above 10 mm, rainfed, leaching)."""
import pytest

from tests.unit._f4 import run, vector_params


@pytest.mark.parametrize("v", vector_params("f4_advice.json"))
def test_given_a_shared_vector_when_computing_the_advice_then_python_matches_the_ts_expectation(v):
    run(v, "app.domain.irrigation_advice")
