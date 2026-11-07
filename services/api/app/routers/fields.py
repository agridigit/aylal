"""Field (parcel) routes, F2 (specs/003-fields-crops/contracts/openapi.yaml).

Every route sits behind farm_context / field_context / require(action): non-member -> 404 identical
to an unknown farm, worker on a field that is not assigned or archived -> 404, worker on a
management action -> 403.
"""
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import text

from app.auth.farm_context import NOT_FOUND, FarmContext, farm_context, field_context, require
from app.fields import service
from app.fields.service import FIELD_COLS, FieldError

_REQUIRE_FIELD_CREATE = require("field.create")
_REQUIRE_FIELD_MERGE = require("field.merge")
_FIELD_CONTEXT_VISIBLE = field_context()
_FIELD_CONTEXT_FIELD_UPDATE = field_context("field.update")
_FIELD_CONTEXT_FIELD_ARCHIVE = field_context("field.archive")
_REQUIRE_FIELD_RESTORE = require("field.restore")
router = APIRouter(prefix="/farms/{farm_id}/fields")


def http_error(e: FieldError) -> HTTPException:
    return HTTPException(status_code=e.status, detail=e.code)


@router.get("")
async def list_fields(ctx: FarmContext = Depends(farm_context)) -> dict[str, Any]:
    sql = f"SELECT {FIELD_COLS} FROM parcels WHERE farm_id = :f AND archived_at IS NULL"
    if ctx.role == "worker":
        sql += " AND id IN (SELECT parcel_id FROM worker_parcels WHERE farm_id = :f AND user_id = :u)"
    rows = (await ctx.session.execute(text(sql + " ORDER BY name, id"), {"f": ctx.farm_id, "u": ctx.user_id})).mappings().all()
    return {"items": [dict(r) for r in rows]}


@router.post("", status_code=201)
async def create_field(body: dict[str, Any], ctx: FarmContext = Depends(_REQUIRE_FIELD_CREATE)) -> dict[str, Any]:
    try:
        created = await service.create_field(ctx.session, ctx.farm_id, ctx.user_id, body)
    except FieldError as e:
        raise http_error(e) from None
    await ctx.session.commit()
    return created


@router.get("/archived")
async def list_archived(ctx: FarmContext = Depends(farm_context)) -> dict[str, Any]:
    if ctx.role == "worker":
        raise NOT_FOUND
    rows = (await ctx.session.execute(
        text(f"SELECT {FIELD_COLS} FROM parcels WHERE farm_id = :f AND archived_at IS NOT NULL ORDER BY archived_at DESC, id"),
        {"f": ctx.farm_id},
    )).mappings().all()
    return {"items": [dict(r) for r in rows]}


@router.post("/merge")
async def merge(body: dict[str, Any], ctx: FarmContext = Depends(_REQUIRE_FIELD_MERGE)) -> dict[str, Any]:
    try:
        merged = await service.merge_fields(ctx.session, ctx.farm_id, body.get("survivor_id"), body.get("merged_ids"))
    except FieldError as e:
        raise http_error(e) from None
    await ctx.session.commit()
    return merged


@router.get("/{field_id}")
async def get_field(field_id: uuid.UUID, ctx: FarmContext = Depends(_FIELD_CONTEXT_VISIBLE)) -> dict[str, Any]:
    return await service.get_field(ctx.session, ctx.farm_id, field_id)


@router.patch("/{field_id}")
async def patch_field(field_id: uuid.UUID, body: dict[str, Any], ctx: FarmContext = Depends(_FIELD_CONTEXT_FIELD_UPDATE)) -> dict[str, Any]:
    try:
        updated = await service.update_field(ctx.session, ctx.farm_id, field_id, body)
    except FieldError as e:
        raise http_error(e) from None
    await ctx.session.commit()
    return updated


@router.delete("/{field_id}", status_code=204)
async def archive_field(field_id: uuid.UUID, ctx: FarmContext = Depends(_FIELD_CONTEXT_FIELD_ARCHIVE)) -> Response:
    await service.archive_field(ctx.session, ctx.farm_id, field_id)
    await ctx.session.commit()
    return Response(status_code=204)


@router.post("/{field_id}/restore")
async def restore_field(field_id: uuid.UUID, ctx: FarmContext = Depends(_REQUIRE_FIELD_RESTORE)) -> dict[str, Any]:
    try:
        restored = await service.restore_field(ctx.session, ctx.farm_id, field_id)
    except FieldError as e:
        raise http_error(e) from None
    await ctx.session.commit()
    return restored
