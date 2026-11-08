"""T055 - R3-A1: the initial history covers the last 12 months, never more (G4 initial window)."""
import datetime as dt

from app.monitoring.imagery import backfill_window


def test_given_today_when_computing_the_initial_window_then_it_spans_12_months_ending_today():
    start, end = backfill_window(dt.date(2026, 12, 5))
    assert end == dt.date(2026, 12, 5) and start == dt.date(2025, 12, 5)


def test_given_the_29th_of_february_when_computing_then_the_start_is_a_valid_date_within_12_months():
    start, end = backfill_window(dt.date(2028, 2, 29))
    assert (end - start).days <= 366 and start.year == 2027
