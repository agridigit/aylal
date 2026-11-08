"""F3 parcel status and vigor (series, comparison, signed map, reprocessing)."""
import datetime as dt
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from app.auth.client_ip import client_ip
from app.auth.farm_context import FarmContext
from app.domain.monitoring_limits import LIMITS, within_limit
from app.monitoring import limits, service
from app.monitoring.access import parcel_access

_FROM = Query(default=None, alias="from")
router = APIRouter(prefix="/farms/{farm_id}/parcels/{parcel_id}")
_PARCEL_ACCESS_STATUS_READ = parcel_access("status.read")
_PARCEL_ACCESS_VIGOR_READ_HISTORY_TRUE = parcel_access("vigor.read", history=True)
_PARCEL_ACCESS_IMAGERY_REPROCESS = parcel_access("imagery.reprocess")
__all__ = ["client_ip", "router"]


@router.get("/status")
async def get_status(parcel_id: uuid.UUID, ctx: FarmContext = Depends(_PARCEL_ACCESS_STATUS_READ)) -> Any:
    return await service.parcel_status(ctx, parcel_id)


@router.get("/vigor")
async def get_vigor(
    request: Request,
    parcel_id: uuid.UUID,
    from_: dt.date | None = _FROM,
    to: dt.date | None = None,
    ctx: FarmContext = Depends(_PARCEL_ACCESS_VIGOR_READ_HISTORY_TRUE),
) -> Any:
    end = to or dt.datetime.now(dt.UTC).date()
    first = end.year * 12 + end.month - 1 - (LIMITS["series_months"] - 1)  # default window: the last 24 calendar months
    start = from_ or dt.date(first // 12, first % 12 + 1, 1)
    if start > end or not within_limit("series_months", service.months_between(start, end)):
        return JSONResponse({"detail": "window_too_long"}, status_code=422)  # refused before any read
    await limits.limit("series", request, ctx.user_id, ctx.farm_id)
    return await service.vigor_series(ctx, parcel_id, start, end)


@router.get("/vigor/compare")
async def compare(request: Request, parcel_id: uuid.UUID, ctx: FarmContext = Depends(_PARCEL_ACCESS_VIGOR_READ_HISTORY_TRUE)) -> Any:
    await limits.limit("compare", request, ctx.user_id, ctx.farm_id)
    return await service.vigor_compare(ctx, parcel_id)


@router.get("/vigor/scenes/{scene_id}/map")
async def scene_map(parcel_id: uuid.UUID, scene_id: uuid.UUID, ctx: FarmContext = Depends(_PARCEL_ACCESS_VIGOR_READ_HISTORY_TRUE)) -> Any:
    return await service.map_url(ctx, parcel_id, scene_id)


@router.post("/vigor/reprocess", status_code=202)
async def reprocess(request: Request, parcel_id: uuid.UUID, ctx: FarmContext = Depends(_PARCEL_ACCESS_IMAGERY_REPROCESS)) -> Any:
    await limits.limit("reprocess", request, ctx.user_id, ctx.farm_id)
    try:
        job = await service.request_reprocess(ctx, parcel_id)
    except service.QuotaExceeded as e:
        raise HTTPException(status_code=429, detail={"code": e.code}, headers={"Retry-After": "3600"}) from e
    return {"job_id": str(job), "limit": LIMITS["reprocess_per_parcel_day"]}
