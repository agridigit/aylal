"""Single farm-scoped access dependency (F1 guard-rail 2).

The role is read from the database on every request. A non-member (including a removed member)
gets the same 404 as for an unknown farm: no existence leak. A member whose role does not allow
the action gets 403.
"""
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from fastapi import Depends, HTTPException
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
