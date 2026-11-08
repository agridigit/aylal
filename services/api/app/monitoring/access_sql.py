"""Single SQL source of the visibility rule (G1): the API (via access.py) and the worker image (copy of this file) read it.

A parcel is visible when it is not archived and, for a worker, assigned to the caller. Binds: :farm, :staff (boolean),
:uid. Named binds only and no `::` cast, so the same text runs under SQLAlchemy and, once converted, under asyncpg.
"""
import re
from collections.abc import Mapping
from typing import Any

STAFF_ROLES = frozenset({"owner", "manager"})
VISIBLE_PARCELS_SQL = (
    "SELECT p.id FROM parcels p WHERE p.farm_id = :farm AND p.archived_at IS NULL"
    " AND (CAST(:staff AS boolean) OR EXISTS (SELECT 1 FROM worker_parcels w"
    " WHERE w.farm_id = p.farm_id AND w.parcel_id = p.id AND w.user_id = :uid))"
)
_BIND = re.compile(r"(?<!:):([a-z_][a-z0-9_]*)")


def scope_params(farm_id: Any, user_id: Any, role: str) -> dict[str, Any]:
    return {"farm": farm_id, "uid": user_id, "staff": role in STAFF_ROLES}


def asyncpg_query(sql: str, params: Mapping[str, Any]) -> tuple[str, list[Any]]:
    """Turn `:name` binds into `$n` for asyncpg; a bind used twice keeps one position."""
    order: list[str] = []

    def number(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in order:
            order.append(name)
        return f"${order.index(name) + 1}"

    return _BIND.sub(number, sql), [params[name] for name in order]
