"""Plan computation entry points of the API side (tests, scheduled jobs): the engine does the work through a SQLAlchemy adapter.
Time is the injected clock; the nightly run is at 03:00 local and the advice is `ready before 7` when computed before 07:00."""
import datetime as dt
import uuid
from collections.abc import Mapping
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.farm_context import FarmContext
from app.domain.clock import FARM_TZ, Clock, is_before_local_hour, local_day
from app.irrigation import engine
from app.irrigation.access import visible_parcels

RUN_HOUR = 3
READY_HOUR = engine.READY_HOUR
_SYSTEM_USER = uuid.UUID(int=0)


class SqlaDb:
    """Adapter giving the engine the two calls it needs on the caller's transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def fetch(self, sql: str, params: Mapping[str, Any]) -> list[dict[str, Any]]:
        return [dict(r) for r in (await self.session.execute(text(sql), dict(params))).mappings().all()]

    async def execute(self, sql: str, params: Mapping[str, Any]) -> None:
        await self.session.execute(text(sql), dict(params))


async def compute_parcel_plan(session: AsyncSession, farm_id: uuid.UUID, parcel_id: uuid.UUID, clock: Clock, from_date: dt.date | None = None) -> dict[str, Any] | None:
    return await engine.compute_parcel_plan(SqlaDb(session), farm_id, parcel_id, clock, from_date)


async def parcels_to_compute(session: AsyncSession, farm_id: uuid.UUID) -> list[uuid.UUID]:
    """Every parcel the farm's owner scope sees: an archived parcel is neither computed nor notified."""
    return await visible_parcels(FarmContext(farm_id, _SYSTEM_USER, "owner", session))


def ready_before_7(t: dt.datetime) -> bool:
    return is_before_local_hour(t, READY_HOUR)


def scheduled_run_at(t: dt.datetime) -> dt.datetime:
    """Next 03:00 local at or after `t` (zone database, never a fixed offset)."""
    run = dt.datetime.combine(local_day(t), dt.time(RUN_HOUR, 0), tzinfo=FARM_TZ)
    return run if run >= t else dt.datetime.combine(local_day(t) + dt.timedelta(days=1), dt.time(RUN_HOUR, 0), tzinfo=FARM_TZ)
