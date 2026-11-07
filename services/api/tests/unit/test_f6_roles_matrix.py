"""T006 - F6 rights matrix: Python mirrors the TS shared vectors f6_roles.json."""
import json
import os
from pathlib import Path

import pytest

DOMAIN_DIR = Path(os.environ.get("AYLAL_DOMAIN_DIR", "/packages/domain"))


def _vec(name: str):
    return json.loads((DOMAIN_DIR / "vectors" / name).read_text(encoding="utf-8"))

VECTORS = _vec("f6_roles.json")


@pytest.mark.parametrize("v", VECTORS, ids=lambda v: f"{v['role']}:{v['action']}")
def test_given_a_role_when_checking_an_f6_action_then_python_matches_the_ts_matrix(v):
    from app.domain.roles import can

    assert can(v["role"], v["action"]) is v["allowed"]


def test_given_any_role_then_physical_deletion_of_an_operation_is_never_allowed():
    from app.domain.roles import can

    assert not any(can(r, "operation.delete") for r in ("owner", "manager", "worker"))


def test_given_f1_and_f2_actions_then_their_matrices_are_unchanged():
    from app.domain.roles import can

    assert can("owner", "farm.delete") and not can("manager", "farm.delete") and can("manager", "field.create")
