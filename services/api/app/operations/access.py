"""Scoped access to operations (G1): one place for REST, sync, account export and the DAR.

A worker sees only its own lines (`author_id`), on parcels assigned to it and not archived. Owner and manager
see every line of the farm, archived or merged parcels included.
"""
import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

STAFF = frozenset({"owner", "manager"})


def visible_lines(role: str, alias: str = "l") -> str:
    """SQL predicate on an `operation_parcels` alias; binds :uid when the role is not staff."""
    if role in STAFF:
        return "TRUE"
    return (
        f"({alias}.author_id = :uid AND {alias}.parcel_archived_at IS NULL AND EXISTS (SELECT 1 FROM worker_parcels w"
        f" WHERE w.farm_id = {alias}.farm_id AND w.parcel_id = {alias}.parcel_id AND w.user_id = :uid))"
    )


async def usable_parcels(
    session: AsyncSession, farm_id: uuid.UUID, user_id: uuid.UUID, role: str, ids: list[uuid.UUID]
) -> list[dict[str, Any]]:
    """Parcels of the farm the caller may record on: not archived; a worker only its assigned ones."""
    query = (
        "SELECT p.id, p.name, COALESCE(p.area_calc_ha, p.area_declared_ha) AS area_ha,"
        " (SELECT c.slug FROM seasons s JOIN crops c ON c.id = s.crop_id WHERE s.field_id = p.id AND s.farm_id = p.farm_id"
        "  AND s.ended_at IS NULL ORDER BY s.started_at DESC LIMIT 1) AS crop_slug,"
        " (SELECT c.name_fr FROM seasons s JOIN crops c ON c.id = s.crop_id WHERE s.field_id = p.id AND s.farm_id = p.farm_id"
        "  AND s.ended_at IS NULL ORDER BY s.started_at DESC LIMIT 1) AS crop_name"
        " FROM parcels p WHERE p.farm_id = :farm AND p.id = ANY(:ids) AND p.archived_at IS NULL"
    )
    if role not in STAFF:
        query += (
            " AND EXISTS (SELECT 1 FROM worker_parcels w WHERE w.farm_id = p.farm_id AND w.parcel_id = p.id"
            " AND w.user_id = :uid)"
        )
    rows = (await session.execute(text(query), {"farm": farm_id, "ids": ids, "uid": user_id})).mappings().all()
    return [dict(r) for r in rows]


async def load_operation(session: AsyncSession, farm_id: uuid.UUID, operation_id: uuid.UUID) -> dict[str, Any] | None:
    """The operation, only when it belongs to this farm."""
    row = (
        await session.execute(
            text("SELECT * FROM operations WHERE id = :i AND farm_id = :f"), {"i": operation_id, "f": farm_id}
        )
    ).mappings().first()
    return dict(row) if row else None


async def lines_of(
    session: AsyncSession, farm_id: uuid.UUID, operation_id: uuid.UUID, user_id: uuid.UUID, role: str
) -> list[dict[str, Any]]:
    """The lines of an operation the caller may see (none for an invisible operation)."""
    rows = (
        await session.execute(
            text(
                "SELECT l.* FROM operation_parcels l WHERE l.farm_id = :f AND l.operation_id = :o"
                f" AND {visible_lines(role)} ORDER BY l.parcel_id"
            ),
            {"f": farm_id, "o": operation_id, "uid": user_id},
        )
    ).mappings().all()
    return [dict(r) for r in rows]


async def can_see(session: AsyncSession, farm_id: uuid.UUID, operation_id: uuid.UUID, user_id: uuid.UUID, role: str) -> bool:
    if role in STAFF:
        return True
    return bool(await lines_of(session, farm_id, operation_id, user_id, role))
