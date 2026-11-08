"""T006 - G4: F3 caps; Python mirrors the TS shared vectors f3_limits.json."""
import json
import os
from pathlib import Path

import pytest

DOMAIN_DIR = Path(os.environ.get("AYLAL_DOMAIN_DIR", "/packages/domain"))
VECTORS = json.loads((DOMAIN_DIR / "vectors" / "f3_limits.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("v", VECTORS, ids=lambda v: f"{v['rule']}={v['value']}")
def test_given_a_rule_when_checking_a_value_then_python_matches_the_ts_vector(v):
    from app.domain.monitoring_limits import within_limit

    assert within_limit(v["rule"], v["value"]) is v["valid"]


def test_given_the_limits_then_page_default_is_50_and_max_100():
    from app.domain.monitoring_limits import LIMITS

    assert (LIMITS["page_default"], LIMITS["page_max"]) == (50, 100)


def test_given_an_unknown_rule_then_it_is_refused():
    from app.domain.monitoring_limits import within_limit

    assert within_limit("nope", 1) is False
