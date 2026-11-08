"""F3 zones to check, observations and photo deposit."""
import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import JSONResponse

from app.auth.client_ip import client_ip
from app.auth.farm_context import FarmContext
from app.domain.monitoring_limits import LIMITS, within_limit
from app.monitoring import cache, limits, service, uploads
from app.monitoring.access import farm_access, zone_access
from app.monitoring.schemas import ObservationInput

_PHOTO = File(...)
router = APIRouter(prefix="/farms/{farm_id}")
_FARM_ACCESS_ZONE_READ = farm_access("zone.read")
_ZONE_ACCESS_ZONE_DISMISS = zone_access("zone.dismiss")
_ZONE_ACCESS_ZONE_OBSERVE = zone_access("zone.observe")
__all__ = ["client_ip", "router"]


@router.get("/zones")
async def list_zones(limit: int = Query(default=LIMITS["page_default"]), ctx: FarmContext = Depends(_FARM_ACCESS_ZONE_READ)) -> Any:
    if not within_limit("limit", limit):
        return JSONResponse({"detail": "limit_out_of_range"}, status_code=422)
    return await service.zones(ctx, limit)


@router.post("/zones/{zone_id}/dismiss")
async def dismiss_zone(zone_id: uuid.UUID, ctx: FarmContext = Depends(_ZONE_ACCESS_ZONE_DISMISS)) -> Any:
    return await service.dismiss(ctx, "attention_zones", zone_id)


@router.post("/zones/{zone_id}/observations/photo", status_code=201)
async def deposit_photo(request: Request, photo: UploadFile = _PHOTO, ctx: FarmContext = Depends(_ZONE_ACCESS_ZONE_OBSERVE)) -> Any:
    await limits.limit("photo", request, ctx.user_id, ctx.farm_id)
    data = await photo.read(LIMITS["photo_bytes"] + 1)
    if len(data) > LIMITS["photo_bytes"]:
        raise HTTPException(status_code=413, detail={"code": "payload_too_large"})
    if uploads.sniff_image(data) is None:
        raise HTTPException(status_code=415, detail={"code": "unsupported_image"})
    photo_id = await uploads.deposit_photo(ctx.session, ctx.farm_id, ctx.user_id, data)
    await ctx.session.commit()
    return {"photo_id": str(photo_id)}


@router.post("/zones/{zone_id}/observations", status_code=201)
async def add_observation(zone_id: uuid.UUID, body: ObservationInput, ctx: FarmContext = Depends(_ZONE_ACCESS_ZONE_OBSERVE)) -> Any:
    try:
        created = await service.create_observation(ctx.session, ctx.farm_id, ctx.user_id, zone_id, body.id, body.note, body.photo_id)
    except service.QuotaExceeded as e:
        await ctx.session.rollback()
        raise HTTPException(status_code=429, detail={"code": e.code}, headers={"Retry-After": "3600"}) from e
    except uploads.InvalidObjectRef as e:
        await ctx.session.rollback()
        raise HTTPException(status_code=422, detail={"code": "invalid_object_ref"}) from e
    await ctx.session.commit()
    await cache.bump_data_version(ctx.farm_id)
    return {"id": str(body.id), "zone_id": str(zone_id), "created": created}
