"""F4 irrigation events: record (creates the linked F6 operation), history and cancellation (never a delete)."""
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

from app.auth.client_ip import client_ip
from app.auth.farm_context import FarmContext
from app.domain.clock import Clock, get_clock
from app.irrigation import http, limits, service
from app.irrigation.access import parcel_access
from app.irrigation.schemas import IrrigationEventInput

router = APIRouter(prefix="/farms/{farm_id}/parcels/{parcel_id}/irrigation")
_RECORD = parcel_access("irrigation.record")
_CORRECT = parcel_access("irrigation.correct")
_READ = parcel_access("advice.read")
__all__ = ["client_ip", "router"]


@router.post("/events")
async def record_irrigation(
    request: Request, parcel_id: uuid.UUID, body: IrrigationEventInput, ctx: FarmContext = Depends(_RECORD), clock: Clock = Depends(get_clock)
) -> Any:
    await limits.limit("record", request, ctx.user_id, ctx.farm_id)
    now = clock.now()
    out = await http.write(ctx, lambda: service.record_event(ctx.session, ctx.farm_id, ctx.user_id, parcel_id, body, now))
    if isinstance(out, JSONResponse):
        return out
    event, created = out
    return JSONResponse(event, status_code=201 if created else 200)


@router.get("/events")
async def list_events(
    request: Request, parcel_id: uuid.UUID, limit: int = Query(default=http.DEFAULT_PAGE), cursor: str | None = None, ctx: FarmContext = Depends(_READ)
) -> Any:
    paging = http.page(limit, cursor)
    if paging is None:
        return http.bad_limit()
    await limits.limit("history", request, ctx.user_id, ctx.farm_id)
    return JSONResponse(await service.list_events(ctx.session, ctx.farm_id, ctx.user_id, ctx.role, parcel_id, *paging))


@router.post("/events/{event_id}/cancel")
async def cancel_irrigation(
    parcel_id: uuid.UUID, event_id: uuid.UUID, ctx: FarmContext = Depends(_CORRECT), clock: Clock = Depends(get_clock)
) -> Any:
    now = clock.now()
    return await http.write(ctx, lambda: service.cancel_event(ctx.session, ctx.farm_id, ctx.user_id, ctx.role, parcel_id, event_id, now))
