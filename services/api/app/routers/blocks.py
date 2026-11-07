"""Block / irrigation sector routes (F2), nested under an active, visible field."""
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Response
from sqlalchemy import text

from app.auth.farm_context import FarmContext, field_context
from app.fields import service
from app.fields.service import BLOCK_COLS, FieldError
from app.routers.fields import http_error

_FIELD_CONTEXT_VISIBLE = field_context()
_FIELD_CONTEXT_FIELD_SPLIT = field_context("field.split")
router = APIRouter(prefix="/farms/{farm_id}/fields/{field_id}/blocks")


@router.get("")
async def list_blocks(field_id: uuid.UUID, ctx: FarmContext = Depends(_FIELD_CONTEXT_VISIBLE)) -> dict[str, Any]:
    rows = (await ctx.session.execute(
        text(f"SELECT {BLOCK_COLS} FROM field_blocks WHERE farm_id = :f AND field_id = :fi AND archived_at IS NULL ORDER BY name, id"),
        {"f": ctx.farm_id, "fi": field_id},
    )).mappings().all()
    return {"items": [dict(r) for r in rows]}


@router.post("", status_code=201)
async def create_block(field_id: uuid.UUID, body: dict[str, Any], ctx: FarmContext = Depends(_FIELD_CONTEXT_FIELD_SPLIT)) -> dict[str, Any]:
    try:
        block = await service.create_block(ctx.session, ctx.farm_id, field_id, body)
    except FieldError as e:
        raise http_error(e) from None
    await ctx.session.commit()
    return block


@router.patch("/{block_id}")
async def patch_block(field_id: uuid.UUID, block_id: uuid.UUID, body: dict[str, Any], ctx: FarmContext = Depends(_FIELD_CONTEXT_FIELD_SPLIT)) -> dict[str, Any]:
    try:
        block = await service.update_block(ctx.session, ctx.farm_id, field_id, block_id, body)
    except FieldError as e:
        raise http_error(e) from None
    await ctx.session.commit()
    return block


@router.delete("/{block_id}", status_code=204)
async def delete_block(field_id: uuid.UUID, block_id: uuid.UUID, ctx: FarmContext = Depends(_FIELD_CONTEXT_FIELD_SPLIT)) -> Response:
    try:
        await service.delete_block(ctx.session, ctx.farm_id, field_id, block_id)
    except FieldError as e:
        raise http_error(e) from None
    await ctx.session.commit()
    return Response(status_code=204)
