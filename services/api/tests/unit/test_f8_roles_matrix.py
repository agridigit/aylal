"""T007 - G1: F8 rights matrix mirrors the TS vectors f8_roles.json; earlier matrices unchanged."""
import pytest

from tests.unit._f8 import load


@pytest.mark.parametrize("v", load("f8_roles.json"), ids=lambda v: f"{v['role']}:{v['action']}")
def test_given_a_role_when_checking_an_f8_action_then_python_matches_the_ts_matrix(v):
    from app.domain.roles import can

    assert can(v["role"], v["action"]) is v["allowed"]


def test_given_the_worker_then_no_financial_action_is_allowed_but_harvest_write_is():
    from app.domain.roles import can

    fin = [v["action"] for v in load("f8_roles.json") if v["role"] == "worker" and v["action"].split(".")[0] in ("expense", "sale", "economics", "stock", "market_price", "receipt")]
    assert len(fin) >= 10 and not any(can("worker", a) for a in fin)
    assert can("worker", "harvest.write") and not can("worker", "harvest.correct")


def test_given_any_role_then_no_f8_registry_row_can_be_deleted():
    from app.domain.roles import can

    assert can("owner", "expense.write")  # the matrix knows F8
    assert not any(can(r, a) for r in ("owner", "manager", "worker") for a in ("expense.delete", "sale.delete", "harvest.delete", "stock_movement.delete"))


def test_given_earlier_matrices_then_they_are_unchanged():
    from app.domain.roles import can

    assert can("owner", "farm.delete") and not can("manager", "farm.delete")
    assert can("worker", "operation.create") and not can("worker", "operation.validate")
    assert not can("worker", "finance.read") and can("manager", "finance.read")
