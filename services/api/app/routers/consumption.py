"""F4 water consumption: aggregates on the caller's visible parcels only (a worker never gets a farm total)."""
import datetime as dt
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import JSONResponse

from app.auth.client_ip import client_ip
from app.auth.farm_context import FarmContext
from app.domain.clock import Clock, get_clock, local_day
from app.domain.irrigation_limits import LIMITS
from app.irrigation import http, limits
from app.irrigation.access import farm_access
from app.irrigation.consumption import add_months, consumption

router = APIRouter(prefix="/farms/{farm_id}")
_READ = farm_access("consumption.read")
_FROM = Query(default=None, alias="from")
__all__ = ["client_ip", "router"]


@router.get("/irrigation/consumption")
async def get_consumption(
    request: Request, season_id: uuid.UUID | None = None, from_: dt.date | None = _FROM, to: dt.date | None = None,
    limit: int = Query(default=http.DEFAULT_PAGE), cursor: str | None = None,
    ctx: FarmContext = Depends(_READ), clock: Clock = Depends(get_clock),
) -> Any:
    paging = http.page(limit, cursor)
    if paging is None:
        return http.bad_limit()
    now = clock.now()
    last = to or local_day(now)
    first = from_ or add_months(last, -LIMITS["window_months"])
    if first > last or add_months(first, LIMITS["window_months"]) < last:
        return JSONResponse({"detail": "window_too_long"}, status_code=422)  # refused before any read
    await limits.limit("consumption", request, ctx.user_id, ctx.farm_id)
    body, etag = await consumption(ctx, first, last, season_id, *paging, now)
    quoted = f'"{etag}"'
    if request.headers.get("if-none-match") == quoted:
        return Response(status_code=304, headers={"ETag": quoted})
    return JSONResponse(body, headers={"ETag": quoted})
