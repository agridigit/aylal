"""T074 (US5) - Python mirror of packages/domain/tests/water-analysis-us5.test.ts."""
from app.domain.irrigation_advice import compute_advice
from app.domain.leaching import leaching_fraction

CROP = {"ece_threshold_ds_m": 2, "ece_max_ds_m": 8, "leaching_max": 0.15}
SYSTEM = {"efficiency": 0.9, "rate_mm_h": 4, "sectors_count": 1}


def _advise(lr):
    return compute_advice({"irrigated": True, "greenhouse": False, "has_system": True, "system": SYSTEM, "depletion_mm": 30, "raw_mm": 25,
                           "rain_mm_today": 0, "leaching_fraction": lr, "stress_watch_ratio": 0.5})


def _wa():
    import app.domain.water_analysis as module

    return module


def test_given_a_salinity_above_the_threshold_then_lr_follows_fao29_and_the_duration_is_longer():
    lr = leaching_fraction({"ecw_ds_m": 3.1, **CROP})["leaching_fraction"]
    assert abs(lr - 3.1 / (40 - 3.1)) < 1e-4 and _advise(lr)["total_minutes"] > _advise(0)["total_minutes"]


def test_given_a_salinity_at_the_threshold_then_no_leaching_is_added():
    assert leaching_fraction({"ecw_ds_m": 2, **CROP})["leaching_fraction"] == 0
    assert _advise(0)["total_minutes"] == _advise(None)["total_minutes"]


def test_given_a_missing_salinity_reference_then_there_is_no_leaching_and_the_reason_is_given():
    out = leaching_fraction({"ecw_ds_m": 3.1, "ece_threshold_ds_m": 2, "ece_max_ds_m": None, "leaching_max": 0.15})
    assert out["leaching_fraction"] is None and out["unavailable_reason"] == "no_salinity_reference"


def test_given_an_analysis_then_its_age_is_in_days_and_a_future_date_is_refused():
    assert _wa().analysis_age_days({"analysed_on": "2026-05-01", "today": "2026-06-04"}) == {"age_days": 34}
    assert _wa().analysis_age_days({"analysed_on": "2026-06-05", "today": "2026-06-04"}) == {"age_days": None, "error": "in_the_future"}


def test_given_an_analysis_and_a_fraction_then_the_assumptions_state_salinity_source_age_and_fraction():
    out = _wa().analysis_assumptions({"ec_ds_m": 3.1, "water_source": "well-42", "analysed_on": "2026-05-01", "today": "2026-06-04", "leaching_fraction": 0.084, "unavailable_reason": None})
    assert [a["key"] for a in out] == ["ece_ds_m", "water_source", "analysis_age_days", "leaching_fraction"]
    assert next(a for a in out if a["key"] == "analysis_age_days")["value"] == 34


def test_given_a_missing_salinity_reference_then_the_assumptions_carry_the_reason_and_no_fraction():
    out = _wa().analysis_assumptions({"ec_ds_m": 3.1, "water_source": "", "analysed_on": "2026-05-01", "today": "2026-06-04", "leaching_fraction": None, "unavailable_reason": "no_salinity_reference"})
    assert "leaching_fraction" not in [a["key"] for a in out]
    assert next(a for a in out if a["key"] == "leaching_unavailable_reason")["value"] == "no_salinity_reference"


def test_given_a_referential_limit_then_an_older_analysis_is_old_and_without_a_limit_it_never_is():
    assert _wa().is_old_analysis({"age_days": 400, "max_age_days": 365}) == {"old": True}
    assert _wa().is_old_analysis({"age_days": 400, "max_age_days": None}) == {"old": False}
