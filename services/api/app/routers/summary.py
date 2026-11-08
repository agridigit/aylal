"""F3 daily summary (computed live on the caller's scope) and the caller's own notification settings."""
from typing import Any

from fastapi import APIRouter, Depends, Request

from app.auth.client_ip import client_ip
from app.auth.farm_context import FarmContext
from app.monitoring import limits, service
from app.monitoring.access import farm_access
from app.monitoring.schemas import SummarySettings

router = APIRouter(prefix="/farms/{farm_id}/summary")
_FARM_ACCESS_SUMMARY_READ = farm_access("summary.read")
_FARM_ACCESS_SUMMARY_SETTINGS = farm_access("summary.settings")
__all__ = ["client_ip", "router"]


@router.get("/today")
async def today(request: Request, ctx: FarmContext = Depends(_FARM_ACCESS_SUMMARY_READ)) -> Any:
    await limits.limit("summary", request, ctx.user_id, ctx.farm_id)
    return await service.summary_today(ctx)


@router.put("/settings")
async def settings(body: SummarySettings, ctx: FarmContext = Depends(_FARM_ACCESS_SUMMARY_SETTINGS)) -> Any:
    return await service.save_settings(ctx, body.summary_hour, body.alerts_enabled)
