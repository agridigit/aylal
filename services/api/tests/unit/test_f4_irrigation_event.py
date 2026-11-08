"""T058 (US3) - Python mirror of packages/domain/tests/irrigation-event-us3.test.ts."""
import pytest

from app.domain.irrigation_units import from_duration, from_volume

OK = {"duration_min": 60, "volume_m3": None, "performed_on": "2026-06-03", "today": "2026-06-04", "slot_count": 0, "area_ha": 1}
SYS = {"rate_mm_h": 4, "area_m2": 5000, "efficiency": 0.9}


def _validate(payload):
    from app.domain.irrigation_event import validate_irrigation_event

    return validate_irrigation_event(payload)


def test_given_a_duration_then_the_volume_comes_from_the_installation():
    assert abs(from_duration({"minutes": 60, **SYS})["volume_m3"] - 20) < 0.01


def test_given_a_volume_then_the_duration_is_the_inverse_and_the_round_trip_is_stable():
    volume = from_duration({"minutes": 90, **SYS})["volume_m3"]
    assert from_volume({"volume_m3": volume, **SYS})["minutes"] == 90


def test_given_an_installation_without_a_rate_then_no_duration_is_invented():
    assert from_volume({"volume_m3": 10, "rate_mm_h": None, "area_m2": 5000, "efficiency": 0.9})["minutes"] is None


def test_given_a_coherent_duration_entry_then_it_is_valid_and_not_a_duplicate():
    out = _validate(OK)
    assert out["valid"] is True and out["errors"] == [] and out["possible_duplicate"] is False


@pytest.mark.parametrize("patch", [{"volume_m3": 5}, {"duration_min": None}])
def test_given_both_or_neither_of_duration_and_volume_then_it_is_refused(patch):
    out = _validate({**OK, **patch})
    assert out["valid"] is False and out["errors"][0]["code"] == "exactly_one_of_duration_or_volume"


@pytest.mark.parametrize("minutes,valid", [(1440, True), (1441, False), (0, False)])
def test_given_a_duration_then_the_24_hour_cap_applies(minutes, valid):
    assert _validate({**OK, "duration_min": minutes})["valid"] is valid


@pytest.mark.parametrize("day,valid", [("2026-06-04", True), ("2026-06-05", False), ("2025-04-30", True), ("2025-04-29", False)])
def test_given_a_date_then_no_future_and_at_most_400_days_back(day, valid):
    assert _validate({**OK, "performed_on": day})["valid"] is valid


def test_given_24_events_on_the_day_and_sector_then_the_25th_is_refused_with_the_quota_code():
    out = _validate({**OK, "slot_count": 24})
    assert out["valid"] is False and out["errors"][0]["code"] == "events_per_day_sector"


def test_given_a_volume_above_1000_m3_per_hectare_then_it_is_refused():
    assert _validate({**OK, "duration_min": None, "volume_m3": 1001})["valid"] is False
    assert _validate({**OK, "duration_min": None, "volume_m3": 1000})["valid"] is True


def test_given_one_event_on_the_same_day_and_sector_then_it_stays_valid_but_is_flagged_possible_duplicate():
    out = _validate({**OK, "slot_count": 1})
    assert out["valid"] is True and out["possible_duplicate"] is True


def test_given_an_error_then_the_field_and_an_i18n_key_are_returned():
    e = _validate({**OK, "performed_on": "2026-06-05"})["errors"][0]
    assert e["field"] == "performed_on" and e["i18n_key"].startswith("irrigation.")
