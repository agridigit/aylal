"""Season (campaign) routes (F2), nested under an active, visible field."""
import uuid
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import text

from app.auth.farm_context import FarmContext, field_context
from app.fields import service
from app.fields.service import SEASON_COLS, FieldError
from app.routers.fields import http_error

_FIELD_CONTEXT_VISIBLE = field_context()
_FIELD_CONTEXT_SEASON_START = field_context("season.start")
_FIELD_CONTEXT_SEASON_UPDATE = field_context("season.update")
router = APIRouter(prefix="/farms/{farm_id}/fields/{field_id}/seasons")


@router.get("")
async def list_seasons(field_id: uuid.UUID, ctx: FarmContext = Depends(_FIELD_CONTEXT_VISIBLE)) -> dict[str, Any]:
    rows = (await ctx.session.execute(
        text(f"SELECT {SEASON_COLS} FROM seasons WHERE farm_id = :f AND field_id = :fi ORDER BY started_at DESC, id"),
        {"f": ctx.farm_id, "fi": field_id},
    )).mappings().all()
    return {"items": [dict(r) for r in rows]}


@router.post("", status_code=201)
async def start_season(field_id: uuid.UUID, body: dict[str, Any], ctx: FarmContext = Depends(_FIELD_CONTEXT_SEASON_START)) -> dict[str, Any]:
    try:
        season = await service.create_season(ctx.session, ctx.farm_id, field_id, body)
    except FieldError as e:
        raise http_error(e) from None
    await ctx.session.commit()
    return season


@router.get("/{season_id}")
async def get_season(field_id: uuid.UUID, season_id: uuid.UUID, ctx: FarmContext = Depends(_FIELD_CONTEXT_VISIBLE)) -> dict[str, Any]:
    try:
        return await service.get_season(ctx.session, ctx.farm_id, field_id, season_id)
    except FieldError as e:
        raise http_error(e) from None


@router.patch("/{season_id}")
async def patch_season(field_id: uuid.UUID, season_id: uuid.UUID, body: dict[str, Any], ctx: FarmContext = Depends(_FIELD_CONTEXT_SEASON_UPDATE)) -> dict[str, Any]:
    try:
        season = await service.update_season(ctx.session, ctx.farm_id, field_id, season_id, body)
    except FieldError as e:
        raise http_error(e) from None
    await ctx.session.commit()
    return season
