"""F3 weather alerts (visible parcels only)."""
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from app.auth.farm_context import FarmContext
from app.domain.monitoring_limits import LIMITS, within_limit
from app.monitoring import service
from app.monitoring.access import alert_access, farm_access

router = APIRouter(prefix="/farms/{farm_id}")
_FARM_ACCESS_ALERT_READ = farm_access("alert.read")
_ALERT_ACCESS_ALERT_DISMISS = alert_access("alert.dismiss")


@router.get("/alerts")
async def list_alerts(limit: int = Query(default=LIMITS["page_default"]), ctx: FarmContext = Depends(_FARM_ACCESS_ALERT_READ)) -> Any:
    if not within_limit("limit", limit):
        return JSONResponse({"detail": "limit_out_of_range"}, status_code=422)
    return await service.alerts(ctx, limit)


@router.post("/alerts/{alert_id}/dismiss")
async def dismiss_alert(alert_id: uuid.UUID, ctx: FarmContext = Depends(_ALERT_ACCESS_ALERT_DISMISS)) -> Any:
    return await service.dismiss(ctx, "alerts", alert_id)
