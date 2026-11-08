"""T016 - water balance replay: Python mirrors the shared vectors; 400 days in under 50 ms."""
import time

import pytest

from tests.unit._f4 import run, vector_params


@pytest.mark.parametrize("v", vector_params("f4_water_balance.json"))
def test_given_a_shared_vector_when_replaying_the_balance_then_python_matches_the_ts_expectation(v):
    run(v, "app.domain.water_balance")


def test_given_a_400_day_window_when_replaying_then_it_takes_under_50_ms():
    from app.domain.water_balance import replay_balance

    days = [{"day": f"d{i}", "et0_mm": 5, "kc": 0.8, "rain_eff_mm": 6 if i % 7 == 0 else 0, "irrigation_net_mm": 8 if i % 5 == 0 else 0} for i in range(400)]
    t0 = time.perf_counter()
    out = replay_balance({"taw_mm": 80, "initial_depletion_mm": 0, "days": days})
    assert time.perf_counter() - t0 < 0.05 and len(out["days"]) == 400


def test_given_the_same_inputs_when_replayed_twice_then_the_result_is_identical():
    from app.domain.water_balance import replay_balance

    days = [{"day": "2026-06-01", "et0_mm": 5, "kc": 1, "rain_eff_mm": 0, "irrigation_net_mm": 0}]
    assert replay_balance({"taw_mm": 60, "initial_depletion_mm": 0, "days": days}) == replay_balance({"taw_mm": 60, "initial_depletion_mm": 0, "days": days})
