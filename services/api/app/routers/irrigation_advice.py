"""F4 advice and water balance (read-only: the stored plans are served, nothing is computed and no gateway is called)."""
import datetime as dt
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import JSONResponse

from app.auth.client_ip import client_ip
from app.auth.farm_context import FarmContext
from app.domain.clock import Clock, get_clock, local_day
from app.domain.irrigation_limits import LIMITS
from app.irrigation import http, reading
from app.irrigation.access import farm_access, parcel_access
from app.irrigation.schemas import Advice, AdviceList

router = APIRouter(prefix="/farms/{farm_id}")
_FARM_READ = farm_access("advice.read")
_PARCEL_READ = parcel_access("advice.read")
_FROM = Query(default=None, alias="from")
__all__ = ["client_ip", "router"]


@router.get("/irrigation/advice", response_model=None, responses={200: {"model": AdviceList}})
async def list_advice(
    request: Request, limit: int = Query(default=http.DEFAULT_PAGE), cursor: str | None = None,
    ctx: FarmContext = Depends(_FARM_READ), clock: Clock = Depends(get_clock),
) -> Any:
    paging = http.page(limit, cursor)
    if paging is None:
        return http.bad_limit()
    now = clock.now()
    body, etag = await reading.advice_list(ctx, local_day(now), now, *paging)
    quoted = f'"{etag}"'
    if request.headers.get("if-none-match") == quoted:
        return Response(status_code=304, headers={"ETag": quoted})
    return JSONResponse(body, headers={"ETag": quoted})


@router.get("/parcels/{parcel_id}/irrigation/advice", response_model=None, responses={200: {"model": Advice}})
async def get_advice(parcel_id: uuid.UUID, ctx: FarmContext = Depends(_PARCEL_READ), clock: Clock = Depends(get_clock)) -> Any:
    now = clock.now()
    return JSONResponse(await reading.parcel_advice(ctx, parcel_id, local_day(now), now))


@router.get("/parcels/{parcel_id}/irrigation/balance")
async def get_balance(
    parcel_id: uuid.UUID, from_: dt.date | None = _FROM, to: dt.date | None = None,
    ctx: FarmContext = Depends(_PARCEL_READ), clock: Clock = Depends(get_clock),
) -> Any:
    last = to or local_day(clock.now())
    first = from_ or last - dt.timedelta(days=29)
    if first > last or (last - first).days + 1 > LIMITS["points"]:
        return JSONResponse({"detail": "window_too_long"}, status_code=422)  # refused before any read
    return JSONResponse(await reading.balance(ctx, parcel_id, first, last))
