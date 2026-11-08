"""F4 installation of a parcel: read, replace (with its versions) and history."""
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from app.auth.client_ip import client_ip
from app.auth.farm_context import FarmContext
from app.domain.clock import Clock, get_clock
from app.irrigation import http, service
from app.irrigation.access import parcel_access
from app.irrigation.schemas import IrrigationSystemInput

router = APIRouter(prefix="/farms/{farm_id}/parcels/{parcel_id}", route_class=http.NamedFieldRoute)
_READ = parcel_access("irrigation_system.read")
_WRITE = parcel_access("irrigation_system.write")
__all__ = ["client_ip", "router"]


@router.get("/irrigation-system")
async def get_irrigation_system(parcel_id: uuid.UUID, ctx: FarmContext = Depends(_READ)) -> Any:
    return await service.get_system(ctx.session, ctx.farm_id, parcel_id)


@router.put("/irrigation-system")
async def put_irrigation_system(
    parcel_id: uuid.UUID, body: IrrigationSystemInput, ctx: FarmContext = Depends(_WRITE), clock: Clock = Depends(get_clock)
) -> Any:
    now = clock.now()
    return await http.write(ctx, lambda: service.put_system(ctx.session, ctx.farm_id, ctx.user_id, parcel_id, body, now))


@router.get("/irrigation-system/versions")
async def list_system_versions(
    parcel_id: uuid.UUID, limit: int = Query(default=http.DEFAULT_PAGE), cursor: str | None = None, ctx: FarmContext = Depends(_WRITE)
) -> Any:
    paging = http.page(limit, cursor)
    if paging is None:
        return http.bad_limit()
    return JSONResponse(await service.list_versions(ctx.session, ctx.farm_id, parcel_id, *paging))

