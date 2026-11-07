"""T011 - extended rights matrix (field.*, season.*, crop.create_custom): Python mirrors the TS shared vectors."""
import json
import os
from pathlib import Path

import pytest

DOMAIN_DIR = Path(os.environ.get("AYLAL_DOMAIN_DIR", "/packages/domain"))
VECTORS = json.loads((DOMAIN_DIR / "vectors" / "f2_roles.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("v", VECTORS, ids=lambda v: f"{v['role']}:{v['action']}")
def test_given_a_role_when_checking_an_f2_action_then_python_matches_the_ts_matrix(v):
    from app.domain.roles import can

    assert can(v["role"], v["action"]) is v["allowed"]


def test_given_an_unknown_f2_action_then_nobody_can_do_it():
    from app.domain.roles import can

    assert not any(can(r, "field.teleport") for r in ("owner", "manager", "worker"))


def test_given_f1_actions_then_the_f1_matrix_is_unchanged():
    from app.domain.roles import can

    assert can("owner", "farm.delete") and not can("manager", "farm.delete") and can("worker", "record.write")
