"""T006 - G7: injected clock; local day in Africa/Casablanca; 'before 07:00'; inventory of direct time reads."""
import datetime as dt
import re
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

TZ = ZoneInfo("Africa/Casablanca")
APP = Path(__file__).resolve().parents[2] / "app"
REPO = Path("/repo")
UTC = dt.UTC


def _transitions(year):
    """UTC instants where the Casablanca offset changes, found by scanning the zone database (never hardcoded)."""
    out, t = [], dt.datetime(year, 1, 1, tzinfo=UTC)
    prev = t.astimezone(TZ).utcoffset()
    for _ in range(366 * 24):
        t += dt.timedelta(hours=1)
        off = t.astimezone(TZ).utcoffset()
        if off != prev:
            out.append(t)
        prev = off
    return out


def test_given_a_fixed_clock_when_reading_now_twice_then_the_same_instant_is_returned():
    from app.domain.clock import FixedClock

    c = FixedClock(dt.datetime(2026, 6, 4, 3, 0, tzinfo=UTC))
    assert c.now() == c.now() == dt.datetime(2026, 6, 4, 3, 0, tzinfo=UTC)


def test_given_an_advancing_clock_when_advanced_then_now_moves_by_exactly_that():
    from app.domain.clock import AdvancingClock

    c = AdvancingClock(dt.datetime(2026, 6, 4, 3, 0, tzinfo=UTC))
    c.advance(dt.timedelta(minutes=90))
    assert c.now() == dt.datetime(2026, 6, 4, 4, 30, tzinfo=UTC)


def test_given_a_naive_instant_then_the_clock_refuses_it():
    from app.domain.clock import FixedClock

    with pytest.raises(ValueError):
        FixedClock(dt.datetime(2026, 6, 4, 3, 0))


@pytest.mark.parametrize("iso", ["2026-01-15T23:30:00+00:00", "2026-07-15T23:30:00+00:00"])
def test_given_23_30_utc_in_winter_and_summer_then_the_local_day_follows_the_zone_database(iso):
    from app.domain.clock import local_day

    t = dt.datetime.fromisoformat(iso)
    assert local_day(t) == t.astimezone(TZ).date()


def test_given_the_ramadan_offset_changes_of_the_year_then_the_local_day_and_hour_follow_the_zone_database():
    from app.domain.clock import local_day, local_hour

    changes = _transitions(2026)
    assert len(changes) >= 2
    for t in changes:
        for d in (dt.timedelta(hours=-2), dt.timedelta(0), dt.timedelta(hours=2)):
            assert local_day(t + d) == (t + d).astimezone(TZ).date()
            assert local_hour(t + d) == (t + d).astimezone(TZ).hour


def test_given_local_midnight_then_the_local_day_changes_exactly_there():
    from app.domain.clock import local_day

    start = dt.datetime(2026, 1, 15, tzinfo=UTC)
    found = [m for m in range(1, 24 * 60) if local_day(start + dt.timedelta(minutes=m)) != local_day(start + dt.timedelta(minutes=m - 1))]
    assert len(found) == 1
    assert (start + dt.timedelta(minutes=found[0])).astimezone(TZ).hour == 0


def test_given_every_minute_of_a_day_then_before_7_is_exact():
    from app.domain.clock import is_before_local_hour

    start = dt.datetime(2026, 6, 4, tzinfo=UTC)
    for m in range(24 * 60):
        t = start + dt.timedelta(minutes=m)
        assert is_before_local_hour(t, 7) is (t.astimezone(TZ).hour < 7)


def test_given_the_clock_dependency_then_an_override_provides_the_fixed_clock():
    from app.domain.clock import FixedClock, get_clock, system_clock

    assert get_clock() is system_clock() or get_clock().now().tzinfo is not None  # default: the real clock, tz-aware
    fixed = FixedClock(dt.datetime(2026, 6, 4, 8, 0, tzinfo=UTC))
    from app.main import app

    app.dependency_overrides[get_clock] = lambda: fixed
    try:
        assert app.dependency_overrides[get_clock]().now() == fixed.now()
    finally:
        app.dependency_overrides.pop(get_clock, None)


def test_given_the_f4_sources_then_none_reads_the_system_time_directly():
    pattern = re.compile(r"(\bnow\(\)|Date\.now|datetime\.now|datetime\.utcnow|date\.today|current_date|time\.time\()")
    files = sorted(p for p in (APP / "domain").glob("*.py") if re.search(r"irrigation|water|et0|leaching|clock|advice|application|rainfed|effective", p.name))
    files += sorted((APP / "irrigation").glob("*.py")) + sorted((APP / "sync").glob("irrigation*.py"))
    assert any(p.name == "clock.py" for p in files), "app/domain/clock.py missing"
    assert len(files) >= 5
    for p in files:
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            code = line.split("#", 1)[0]
            if "clock-allow" in line or not code.strip():
                continue  # the single system clock read is annotated
            assert not pattern.search(code), f"{p.relative_to(APP)}:{i} {line.strip()}"


def test_given_the_workers_then_f4_tasks_take_the_clock_not_the_system_time():
    tasks = Path("/repo/services/workers/tasks")
    pattern = re.compile(r"(datetime\.now|date\.today|current_date|\bnow\(\)|time\.time\()")
    for name in ("compute_irrigation_plans", "send_irrigation_reminders"):
        text = (tasks / f"{name}.py").read_text(encoding="utf-8")
        assert "clock" in text, f"{name} does not use the injected clock"
        for i, line in enumerate(text.splitlines(), 1):
            assert not pattern.search(line.split("#", 1)[0]) or "clock-allow" in line, f"{name}:{i}"
