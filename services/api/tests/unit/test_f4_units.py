"""T016 - duration <-> volume conversions: Python mirrors the TS rules on the SAME shared vectors (f4_units.json)."""
import pytest

from tests.unit._f4 import run, vector_params


@pytest.mark.parametrize("v", vector_params("f4_units.json"))
def test_given_a_shared_vector_when_applying_the_rule_then_python_matches_the_ts_expectation(v):
    run(v, "app.domain.irrigation_units")
