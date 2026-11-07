"""Account deletion rules, mirror of packages/domain/src/account-deletion.ts (R8-A1, R8-A3)."""
import datetime as dt
from typing import Any

DELETION_GRACE_DAYS = 30


def deletion_deadline(requested_at: dt.datetime) -> dt.datetime:
    return requested_at + dt.timedelta(days=DELETION_GRACE_DAYS)


def deletion_impact(farms: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Farms the user owns that still have other members: warned before confirming."""
    return [
        {"farm_id": f["farm_id"], "name": f["name"], "other_members": f["other_members"]}
        for f in farms
        if f["role"] == "owner" and f["other_members"] > 0
    ]
