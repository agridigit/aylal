"""T005 - F6 caps (G3): Python mirrors the shared vector f6_limits.json."""
import json
import os
from pathlib import Path

import pytest

DOMAIN_DIR = Path(os.environ.get("AYLAL_DOMAIN_DIR", "/packages/domain"))


def _vec(name: str):
    return json.loads((DOMAIN_DIR / "vectors" / name).read_text(encoding="utf-8"))

VECTORS = _vec("f6_limits.json")


@pytest.mark.parametrize("v", VECTORS, ids=lambda v: f"{v['rule']}={v['value']}")
def test_given_a_rule_when_checking_a_value_then_validity_matches_the_ts_vector(v):
    from datetime import date

    from app.domain.operation_limits import within_limit

    assert within_limit(v["rule"], v["value"], date.fromisoformat(v["today"])) is v["valid"]


def test_given_the_limits_then_defaults_match_the_contract():
    from app.domain.operation_limits import LIMITS

    assert LIMITS["page_default"] == 50 and LIMITS["batch"] == 100 and LIMITS["page_limit"] == 200
