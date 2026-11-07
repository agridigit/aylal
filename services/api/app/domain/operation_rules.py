"""Operation status machine, mirror of packages/domain/src/operation.ts (vectors f6_status_machine.json)."""
import datetime as dt

STAFF = frozenset({"owner", "manager"})
OPERATION_TYPES = (
    "phyto", "fertilization", "irrigation", "tillage", "sowing_planting", "pruning", "weeding", "harvest", "other",
)
_DONE_STATES = frozenset({"done", "pending_validation", "validated"})


def next_status(current: str, action: str, role: str) -> str | None:
    """Next status, or None when the action is not allowed from this state for this role."""
    staff = role in STAFF
    if action == "mark_done":
        return ("validated" if staff else "pending_validation") if current == "planned" else None
    if action == "validate":
        return "validated" if current == "pending_validation" and staff else None
    if action == "cancel":
        if current == "planned":
            return "cancelled"
        return "cancelled" if staff and current in _DONE_STATES else None
    if action == "correct":
        return current if staff and current in _DONE_STATES else None
    return None


def initial_status(performed_on: dt.date, today: dt.date, role: str) -> str:
    if performed_on > today:
        return "planned"
    return "validated" if role in STAFF else "pending_validation"


def is_overdue(status: str, performed_on: dt.date, today: dt.date) -> bool:
    return status == "planned" and performed_on < today
