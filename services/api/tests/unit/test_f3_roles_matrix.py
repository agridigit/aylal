"""T007 - G1: F3 rights matrix mirrors the TS vectors f3_roles.json; no financial field."""
import json
import os
from pathlib import Path

import pytest

DOMAIN_DIR = Path(os.environ.get("AYLAL_DOMAIN_DIR", "/packages/domain"))
VECTORS = json.loads((DOMAIN_DIR / "vectors" / "f3_roles.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("v", VECTORS, ids=lambda v: f"{v['role']}:{v['action']}")
def test_given_a_role_when_checking_an_f3_action_then_python_matches_the_ts_matrix(v):
    from app.domain.roles import can

    assert can(v["role"], v["action"]) is v["allowed"]


def test_given_the_f3_actions_then_none_is_financial():
    assert not [v for v in VECTORS if any(w in v["action"] for w in ("finance", "price", "cost", "amount"))]


def test_given_f1_f2_f6_actions_then_their_matrices_are_unchanged():
    from app.domain.roles import can

    assert can("owner", "farm.delete") and not can("manager", "farm.delete")
    assert can("manager", "field.create") and not can("worker", "field.create")
    assert can("worker", "operation.create") and not can("worker", "operation.validate")
    assert can("owner", "dashboard.read") and not can("worker", "finance.read")
