"""T063 - role rules beyond the shared matrix (R6-A2, FR-022)."""
import pytest

from app.domain.roles import INVITABLE_ROLES, can_assign_parcels_to, can_remove_member


def test_given_the_invitable_roles_then_owner_is_never_one_of_them():
    assert INVITABLE_ROLES == ("manager", "worker")


@pytest.mark.parametrize(
    ("actor", "target", "allowed"),
    [("owner", "manager", True), ("owner", "worker", True), ("owner", "owner", False),
     ("manager", "worker", False), ("manager", "manager", False), ("worker", "worker", False)],
)
def test_given_an_actor_and_a_target_when_removing_then_only_the_owner_removes_and_never_an_owner(actor, target, allowed):
    assert can_remove_member(actor, target) is allowed


@pytest.mark.parametrize(
    ("actor", "target", "allowed"),
    [("owner", "worker", True), ("manager", "worker", True), ("worker", "worker", False),
     ("owner", "manager", False), ("manager", "owner", False)],
)
def test_given_an_actor_and_a_target_when_assigning_parcels_then_only_staff_to_workers(actor, target, allowed):
    assert can_assign_parcels_to(actor, target) is allowed


def test_given_an_unknown_role_or_action_then_everything_is_denied():
    from app.domain.roles import can

    assert can("intruder", "record.write") is False and can("owner", "farm.explode") is False
