"""T031a - registry hardening: retain_until = max(performed_on, recorded date) + retention years."""
import datetime as dt


def test_given_a_backdated_operation_when_computing_retention_then_the_recording_date_is_the_floor():
    from app.operations.registry import retain_until

    performed, recorded = dt.date(2016, 5, 10), dt.date(2026, 5, 10)
    assert retain_until(performed, recorded_on=recorded, years=5) == dt.date(2031, 5, 10)


def test_given_a_future_dated_operation_when_computing_retention_then_performed_on_is_used():
    from app.operations.registry import retain_until

    assert retain_until(dt.date(2027, 3, 1), recorded_on=dt.date(2026, 5, 10), years=5) == dt.date(2032, 3, 1)


def test_given_a_29_february_floor_when_computing_retention_then_it_falls_back_to_the_28th():
    from app.operations.registry import retain_until

    assert retain_until(dt.date(2020, 1, 1), recorded_on=dt.date(2024, 2, 29), years=5) == dt.date(2029, 2, 28)


def test_given_no_years_then_the_configured_retention_is_used(monkeypatch):
    from app.operations.registry import retain_until

    monkeypatch.setenv("AYLAL_REGISTRY_RETENTION_YEARS", "7")
    try:
        from app.config import get_settings

        get_settings.cache_clear()
    except AttributeError:
        pass
    assert retain_until(dt.date(2026, 1, 1), recorded_on=dt.date(2026, 1, 1)) == dt.date(2033, 1, 1)
