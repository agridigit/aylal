"""T034a - G1: worker view of an advice (deny-by-default whitelist), Python mirror of advice-worker-view.ts."""
import json

import pytest

from tests.unit._f4 import DOMAIN_DIR, load, matches, run, vector_params

CASES = load("f4_worker_view.json")
FORBIDDEN = ["ece", "ecw", "salin", "water_source", "analysis_age", "soil", "taw", "raw_mm", "moisture", "leaching", "cost", "x_future"]


@pytest.mark.parametrize("v", vector_params("f4_worker_view.json"))
def test_given_a_shared_vector_when_building_the_worker_view_then_python_matches_the_ts_expectation(v):
    run(v, "app.irrigation.worker_view")


def test_given_the_whitelist_then_it_is_exactly_the_six_documented_keys():
    from app.irrigation.worker_view import WORKER_ASSUMPTION_KEYS

    wl = json.loads((DOMAIN_DIR / "vectors" / "f4_worker_view.json").read_text(encoding="utf-8"))["whitelist"]
    assert sorted(WORKER_ASSUMPTION_KEYS) == sorted(wl)


def test_given_salinity_soil_and_leaching_hypotheses_then_no_forbidden_key_survives_at_any_depth_in_the_worker_view():
    from app.irrigation.worker_view import advice_view

    case = next(c for c in CASES if c["fn"] == "advice_view" and c["input"]["role"] == "worker")
    out = json.dumps(advice_view(json.loads(json.dumps(case["input"]))))
    for k in FORBIDDEN:
        assert f'"{k}' not in out, k


def test_given_an_input_advice_then_the_view_does_not_mutate_it():
    from app.irrigation.worker_view import advice_view

    case = next(c for c in CASES if c["fn"] == "advice_view" and c["input"]["role"] == "worker")
    before = json.dumps(case["input"], sort_keys=True)
    advice_view(case["input"])
    assert json.dumps(case["input"], sort_keys=True) == before


def test_given_staff_then_the_view_is_the_complete_advice():
    from app.irrigation.worker_view import advice_view

    case = next(c for c in CASES if c["fn"] == "advice_view" and c["input"]["role"] == "manager")
    matches(advice_view(case["input"]), case["expected"], exact=True)
