"""T006 - G7: injected clock; farm day in Africa/Casablanca; backdating, future, 13-week window, stale price; no direct time read in F8 rules."""
import datetime as dt
import re
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[2] / "app"
RULES = ["money", "expense_allocation", "farm_economics", "stock_ledger", "weighted_average_cost", "price_trend", "receipt_proposal", "economics_limits", "ledger_rules"]
# 2026-06-04T23:30Z is already 2026-06-05 in Casablanca (UTC+1 in June)
NOW = dt.datetime(2026, 6, 4, 23, 30, tzinfo=dt.UTC)
LOCAL = dt.date(2026, 6, 5)


def _clock():
    from app.domain.clock import FixedClock

    return FixedClock(NOW)


def test_given_a_utc_evening_when_dating_an_entry_then_the_local_farm_day_is_used():
    from app.domain.economics_limits import date_status

    assert date_status(LOCAL, _clock()) == "ok"
    assert date_status(LOCAL + dt.timedelta(days=1), _clock()) == "ok"
    assert date_status(LOCAL + dt.timedelta(days=2), _clock()) == "in_future"


@pytest.mark.parametrize("age,expected", [(800, "ok"), (801, "too_old")])
def test_given_the_backdating_cap_then_800_days_pass_and_801_are_refused(age, expected):
    from app.domain.economics_limits import date_status

    assert date_status(LOCAL - dt.timedelta(days=age), _clock()) == expected


def test_given_the_price_window_then_it_covers_13_weeks_ending_on_the_local_day():
    from app.domain.price_trend import trend_window

    assert trend_window(_clock()) == {"from": (LOCAL - dt.timedelta(days=91)).isoformat(), "to": LOCAL.isoformat(), "weeks": 13}


@pytest.mark.parametrize("age,stale", [(14, False), (15, True)])
def test_given_a_price_then_it_is_stale_after_14_local_days(age, stale):
    from app.domain.price_trend import is_stale_price

    assert is_stale_price(LOCAL - dt.timedelta(days=age), _clock()) is stale


def test_given_an_advancing_clock_then_the_verdict_follows_it_without_a_system_read():
    from app.domain.clock import AdvancingClock
    from app.domain.price_trend import is_stale_price

    clock = AdvancingClock(NOW)
    observed = LOCAL - dt.timedelta(days=14)
    assert is_stale_price(observed, clock) is False
    clock.advance(dt.timedelta(days=1))
    assert is_stale_price(observed, clock) is True


@pytest.mark.parametrize("mod", RULES)
def test_given_an_f8_rule_module_then_it_defines_functions_and_never_reads_the_system_clock(mod):
    path = APP / "domain" / f"{mod}.py"
    assert path.exists(), f"{mod}.py is missing"
    text = path.read_text(encoding="utf-8")
    assert re.search(r"^def \w+", text, re.M), f"{mod}.py defines nothing"
    direct = re.compile(r"(datetime\.now|date\.today|datetime\.utcnow|time\.time\()")
    for i, line in enumerate(text.splitlines(), 1):
        code = line.split("#", 1)[0]
        assert not direct.search(code) or "clock-allow" in line, f"{mod}.py:{i} {line.strip()}"
