"""Crop routes (F2): shared reference (16 crops) plus the free crops of a farm."""
import uuid
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import current_user, farm_role
from app.auth.farm_context import NOT_FOUND, FarmContext, farm_context, require
from app.db.session import get_session
from app.fields import service
from app.fields.service import FieldError
from app.routers.fields import http_error

_REQUIRE_CROP_CREATE_CUSTOM = require("crop.create_custom")
router = APIRouter()


@router.get("/crops")
async def list_crops(
    farm_id: uuid.UUID | None = None,
    user_id: uuid.UUID = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    if farm_id is not None and await farm_role(session, farm_id, user_id) is None:
        raise NOT_FOUND  # same answer as an unknown farm
    return {"items": await service.list_crops(session, farm_id)}


@router.get("/farms/{farm_id}/crops")
async def list_farm_crops(ctx: FarmContext = Depends(farm_context)) -> dict[str, Any]:
    return {"items": await service.list_crops(ctx.session, ctx.farm_id)}


@router.post("/farms/{farm_id}/crops", status_code=201)
async def create_crop(body: dict[str, Any], ctx: FarmContext = Depends(_REQUIRE_CROP_CREATE_CUSTOM)) -> dict[str, Any]:
    try:
        crop = await service.create_crop(ctx.session, ctx.farm_id, ctx.user_id, body)
    except FieldError as e:
        raise http_error(e) from None
    await ctx.session.commit()
    return crop
