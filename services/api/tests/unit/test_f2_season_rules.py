"""T034 - Python mirror of the crop/season rules: stage correction kept, free crop without advice (R2-A3 to R2-A5)."""
import pytest

from app.domain.season_rules import advice_enabled, display_stage, reestimate_stage, season_date

WHEAT = {"cycle": "annual", "stages": [{"key": "emergence", "gdd_from": 0}, {"key": "tillering", "gdd_from": 100}, {"key": "heading", "gdd_from": 400}]}


def test_given_a_corrected_stage_when_the_estimate_is_recomputed_then_the_correction_is_never_overwritten():
    season = {"sowing_date": "2026-01-01", "stage_estimated": "emergence", "stage_corrected": "heading"}
    nxt = reestimate_stage(WHEAT, season, "2026-05-01")
    assert nxt["stage_corrected"] == "heading" and nxt["stage_estimated"] == "tillering"
    assert display_stage(nxt) == "heading"


def test_given_no_correction_when_the_estimate_is_recomputed_then_the_new_estimate_is_displayed():
    nxt = reestimate_stage(WHEAT, {"sowing_date": "2026-01-01", "stage_estimated": "emergence", "stage_corrected": None}, "2026-05-01")
    assert display_stage(nxt) == "tillering"


def test_given_a_free_crop_without_coefficients_when_asking_for_advice_then_it_is_disabled():
    assert advice_enabled({"has_agronomy": False, "stages": []}) is False
    assert advice_enabled({"has_agronomy": True, "stages": WHEAT["stages"]}) is True


@pytest.mark.parametrize(("crop", "inp"), [
    ({"cycle": "perennial"}, {"planting_year": 2018, "sowing_date": "2026-01-01"}),
    ({"cycle": "annual"}, {"planting_year": 2018, "sowing_date": "2026-01-01"}),
])
def test_given_both_a_planting_year_and_a_sowing_date_when_checking_the_cycle_then_it_is_refused(crop, inp):
    assert season_date(crop, inp, "2026-06-01")["ok"] is False
