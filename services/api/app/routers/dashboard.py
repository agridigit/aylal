"""F3 dashboard and weather (read-only, cache only: a user request never reaches a gateway)."""
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import JSONResponse

from app.auth.farm_context import FarmContext
from app.domain.monitoring_limits import LIMITS, within_limit
from app.monitoring import service
from app.monitoring.access import farm_access

router = APIRouter(prefix="/farms/{farm_id}")
_FARM_ACCESS_DASHBOARD_READ = farm_access("dashboard.read")
_FARM_ACCESS_WEATHER_READ = farm_access("weather.read")
_UNPROCESSABLE = 422


@router.get("/dashboard")
async def get_dashboard(
    request: Request,
    limit: int = Query(default=LIMITS["page_default"]),
    cursor: str | None = None,
    ctx: FarmContext = Depends(_FARM_ACCESS_DASHBOARD_READ),
) -> Response:
    offset = int(cursor) if cursor and cursor.isdigit() else 0
    if not within_limit("limit", limit):
        return JSONResponse({"detail": "limit_out_of_range"}, status_code=_UNPROCESSABLE)
    body, etag = await service.dashboard(ctx, limit, offset)
    quoted = f'"{etag}"'
    if request.headers.get("if-none-match") == quoted:
        return Response(status_code=304, headers={"ETag": quoted})
    return JSONResponse(body, headers={"ETag": quoted})


@router.get("/weather")
async def get_weather(
    days: int = Query(default=LIMITS["weather_horizon_days"]), ctx: FarmContext = Depends(_FARM_ACCESS_WEATHER_READ)
) -> Any:
    if not within_limit("weather_horizon_days", days):
        return JSONResponse({"detail": "horizon_must_be_8_days"}, status_code=_UNPROCESSABLE)
    return await service.weather(ctx)
