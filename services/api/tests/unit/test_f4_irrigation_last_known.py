"""T052 (US2) - R2-A6: Python mirror of packages/domain/tests/irrigation-last-known-us2.test.ts (same shared vectors)."""
import importlib

import pytest

from tests.unit._f4 import matches, vector_params


@pytest.mark.parametrize("v", vector_params("f4_us2_last_known.json"))
def test_given_the_shared_vector_then_select_served_plan_matches(v):
    import json

    mod = importlib.import_module("app.domain.irrigation_last_known")
    matches(mod.select_served_plan(json.loads(json.dumps(v["input"]))), v["expected"], v.get("tol", 0.01), v.get("exact", False))


def test_given_the_api_reading_then_it_serves_through_the_shared_rule_and_not_a_private_copy():
    import inspect

    from app.irrigation import reading

    assert "select_served_plan" in inspect.getsource(reading)
