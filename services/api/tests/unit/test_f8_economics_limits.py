"""T008 - G4: F8 caps; Python mirrors the TS shared vectors f8_limits.json."""
import pytest

from tests.unit._f8 import load


@pytest.mark.parametrize("v", load("f8_limits.json"), ids=lambda v: f"{v['rule']}={v['value']}")
def test_given_a_rule_when_checking_a_value_then_python_matches_the_ts_vector(v):
    from app.domain.economics_limits import within_limit

    assert within_limit(v["rule"], v["value"]) is v["valid"]


def test_given_the_limits_then_the_photo_cap_is_6_mib_and_pages_are_50_and_100():
    from app.domain.economics_limits import LIMITS

    assert LIMITS["photo_bytes"] == 6 * 1024 * 1024
    assert (LIMITS["page_default"], LIMITS["page_max"], LIMITS["sync_batch"]) == (50, 100, 100)


def test_given_an_unknown_rule_then_it_is_refused():
    from app.domain.economics_limits import within_limit

    assert within_limit("nope", 1) is False
