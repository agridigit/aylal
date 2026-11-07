"""Single farm-scoped access dependency (F1 guard-rail 2).

The role is read from the database on every request. A non-member (including a removed member)
gets the same 404 as for an unknown farm: no existence leak. A member whose role does not allow
the action gets 403.
"""
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from fastapi import Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.access import current_user, farm_role
from app.db.session import get_session
from app.domain.roles import can

NOT_FOUND = HTTPException(status_code=404, detail="not_found")


@dataclass(frozen=True)
class FarmContext:
    farm_id: uuid.UUID
    user_id: uuid.UUID
    role: str
    session: AsyncSession


async def farm_context(
    farm_id: uuid.UUID,
    user_id: uuid.UUID = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> FarmContext:
    role = await farm_role(session, farm_id, user_id)
    if role is None:
        raise NOT_FOUND
    return FarmContext(farm_id, user_id, role, session)


def require(action: str) -> Callable[..., Awaitable[FarmContext]]:
    """Dependency factory: farm_context plus the rights matrix check for `action`."""

    async def _dep(ctx: FarmContext = Depends(farm_context)) -> FarmContext:
        if not can(ctx.role, action):
            raise HTTPException(status_code=403, detail="forbidden")
        return ctx

    return _dep


def field_context(action: str | None = None, *, archived: bool = False) -> Callable[..., Awaitable[FarmContext]]:
    """Farm context plus visibility of the `field_id` path object, then the role check.

    A field of another farm, unknown, archived (unless `archived`) or, for a worker, not assigned
    is a 404 before any role check (a worker never learns that it exists); then `action` -> 403.
    Children are always loaded with farm_id in the WHERE clause.
    """

    async def _dep(field_id: uuid.UUID, ctx: FarmContext = Depends(farm_context)) -> FarmContext:
        query = "SELECT 1 FROM parcels p WHERE p.id = :f AND p.farm_id = :farm AND p.archived_at IS "
        query += "NOT NULL" if archived else "NULL"
        if ctx.role == "worker":
            query += " AND EXISTS (SELECT 1 FROM worker_parcels w WHERE w.farm_id = p.farm_id AND w.parcel_id = p.id AND w.user_id = :u)"
        found = (await ctx.session.execute(text(query), {"f": field_id, "farm": ctx.farm_id, "u": ctx.user_id})).first()
        if found is None:
            raise NOT_FOUND
        if action is not None and not can(ctx.role, action):
            raise HTTPException(status_code=403, detail="forbidden")
        return ctx

    return _dep
