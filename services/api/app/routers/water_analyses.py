"""F4 water analyses (conductivity): owner and manager only; a worker gets a 403 on a visible parcel and a 404 elsewhere."""
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

from app.auth.client_ip import client_ip
from app.auth.farm_context import FarmContext
from app.domain.clock import Clock, get_clock, local_day
from app.irrigation import http, limits, service
from app.irrigation.access import parcel_access
from app.irrigation.schemas import WaterAnalysisInput

router = APIRouter(prefix="/farms/{farm_id}/parcels/{parcel_id}")
_READ = parcel_access("water_analysis.read")
_WRITE = parcel_access("water_analysis.write")
__all__ = ["client_ip", "router"]


@router.get("/water-analyses")
async def list_water_analyses(
    parcel_id: uuid.UUID, limit: int = Query(default=http.DEFAULT_PAGE), cursor: str | None = None,
    ctx: FarmContext = Depends(_READ), clock: Clock = Depends(get_clock),
) -> Any:
    paging = http.page(limit, cursor)
    if paging is None:
        return http.bad_limit()
    return JSONResponse(await service.list_analyses(ctx.session, ctx.farm_id, parcel_id, local_day(clock.now()), *paging))


@router.post("/water-analyses")
async def add_water_analysis(
    request: Request, parcel_id: uuid.UUID, body: WaterAnalysisInput, ctx: FarmContext = Depends(_WRITE), clock: Clock = Depends(get_clock)
) -> Any:
    await limits.limit("analysis", request, ctx.user_id, ctx.farm_id)
    now = clock.now()
    out = await http.write(ctx, lambda: service.add_analysis(ctx.session, ctx.farm_id, ctx.user_id, parcel_id, body, now))
    if isinstance(out, JSONResponse):
        return out
    analysis, created = out
    return JSONResponse(analysis, status_code=201 if created else 200)
