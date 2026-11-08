"""T007 - G1: F4 rights matrix mirrors the TS vectors f4_roles.json; earlier matrices unchanged."""
import pytest

from tests.unit._f4 import load


@pytest.mark.parametrize("v", load("f4_roles.json"), ids=lambda v: f"{v['role']}:{v['action']}")
def test_given_a_role_when_checking_an_f4_action_then_python_matches_the_ts_matrix(v):
    from app.domain.roles import can

    assert can(v["role"], v["action"]) is v["allowed"]


def test_given_the_f4_actions_then_none_is_financial_and_moisture_ingest_has_no_route_right():
    from app.domain.roles import can

    assert not [v for v in load("f4_roles.json") if any(w in v["action"] for w in ("finance", "price", "cost", "amount"))]
    assert not any(can(r, "moisture.ingest") for r in ("owner", "manager", "worker"))


def test_given_earlier_matrices_then_they_are_unchanged():
    from app.domain.roles import can

    assert can("owner", "farm.delete") and not can("manager", "farm.delete")
    assert can("worker", "operation.create") and not can("worker", "operation.validate")
    assert can("worker", "weather.read") and not can("worker", "finance.read")
