"""Scoped access to monitoring (G1): ONE predicate for REST, sync, export and workers.

`visible_parcels(ctx)` is built on access_sql.VISIBLE_PARCELS_SQL. An invisible object (other farm, unknown, archived,
not assigned to a worker) is a 404 BEFORE the role check (403), so a worker never learns that it exists.
"""
import uuid
from collections.abc import Awaitable, Callable

from fastapi import Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.farm_context import NOT_FOUND, FarmContext, farm_context
from app.domain.roles import can
from app.monitoring.access_sql import STAFF_ROLES, VISIBLE_PARCELS_SQL, scope_params


async def visible_parcels(ctx: FarmContext) -> list[uuid.UUID]:
    """Ids of the parcels the caller sees: not archived, and for a worker only the assigned ones."""
    rows = await ctx.session.execute(text(VISIBLE_PARCELS_SQL), scope_params(ctx.farm_id, ctx.user_id, ctx.role))
    return [r[0] for r in rows.all()]


async def parcel_readable(ctx: FarmContext, parcel_id: uuid.UUID, *, history: bool = False) -> bool:
    """Visible parcel; with `history`, staff may also read the parcel while it is archived (read-only vigor history)."""
    if history and ctx.role in STAFF_ROLES:
        found = await ctx.session.execute(
            text("SELECT 1 FROM parcels WHERE id = :p AND farm_id = :farm"), {"p": parcel_id, "farm": ctx.farm_id}
        )
        return found.first() is not None
    found = await ctx.session.execute(
        text(f"SELECT 1 FROM ({VISIBLE_PARCELS_SQL}) v WHERE v.id = :p"),
        {**scope_params(ctx.farm_id, ctx.user_id, ctx.role), "p": parcel_id},
    )
    return found.first() is not None


def _check_role(ctx: FarmContext, action: str) -> None:
    if not can(ctx.role, action):
        raise HTTPException(status_code=403, detail="forbidden")


def parcel_access(action: str, *, history: bool = False) -> Callable[..., Awaitable[FarmContext]]:
    """Farm context, then visibility of the `parcel_id` path object (404), then the role (403)."""

    async def _dep(parcel_id: uuid.UUID, ctx: FarmContext = Depends(farm_context)) -> FarmContext:
        if not await parcel_readable(ctx, parcel_id, history=history):
            raise NOT_FOUND
        _check_role(ctx, action)
        return ctx

    return _dep


async def parcel_of(session: AsyncSession, table: str, farm_id: uuid.UUID, object_id: uuid.UUID) -> uuid.UUID | None:
    """Parcel of an alert or a zone of THIS farm (farm_id is always in the WHERE clause)."""
    if table not in ("alerts", "attention_zones"):
        raise ValueError(table)
    row = (
        await session.execute(text(f"SELECT parcel_id FROM {table} WHERE id = :i AND farm_id = :f"), {"i": object_id, "f": farm_id})
    ).first()
    return None if row is None else row[0]


async def object_access(ctx: FarmContext, table: str, object_id: uuid.UUID, action: str) -> uuid.UUID:
    """Alert or zone of the farm on a visible parcel (404 otherwise), then the role (403). Returns the parcel id."""
    parcel = await parcel_of(ctx.session, table, ctx.farm_id, object_id)
    if parcel is None or not await parcel_readable(ctx, parcel):
        raise NOT_FOUND
    _check_role(ctx, action)
    return parcel


def alert_access(action: str) -> Callable[..., Awaitable[FarmContext]]:
    async def _dep(alert_id: uuid.UUID, ctx: FarmContext = Depends(farm_context)) -> FarmContext:
        await object_access(ctx, "alerts", alert_id, action)
        return ctx

    return _dep


def zone_access(action: str) -> Callable[..., Awaitable[FarmContext]]:
    async def _dep(zone_id: uuid.UUID, ctx: FarmContext = Depends(farm_context)) -> FarmContext:
        await object_access(ctx, "attention_zones", zone_id, action)
        return ctx

    return _dep


def farm_access(action: str) -> Callable[..., Awaitable[FarmContext]]:
    """Farm-level routes (dashboard, lists, summary): membership (404) then role (403)."""

    async def _dep(ctx: FarmContext = Depends(farm_context)) -> FarmContext:
        _check_role(ctx, action)
        return ctx

    return _dep
