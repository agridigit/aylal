"""HTTP mapping of the F4 refusals (shared by the five routers)."""
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi.responses import JSONResponse

from app.auth.farm_context import FarmContext
from app.domain.irrigation_limits import LIMITS, within_limit
from app.irrigation import cache
from app.irrigation.service import QuotaExceeded, Refusal


def bad_limit() -> JSONResponse:
    return JSONResponse({"detail": "limit_out_of_range"}, status_code=422)


def page(limit: int, cursor: str | None) -> tuple[int, int] | None:
    """(limit, offset) or None when the limit is out of range (refused before any work)."""
    if not within_limit("limit", limit):
        return None
    return limit, int(cursor) if cursor and cursor.isdigit() else 0


async def write(ctx: FarmContext, work: Callable[[], Awaitable[Any]]) -> Any:
    """Run a write in the request transaction: commit and invalidate the cached views, or map the refusal (nothing is kept)."""
    try:
        result = await work()
    except Refusal as e:
        await ctx.session.rollback()
        return JSONResponse({"detail": "validation", "field": e.field, "code": e.code}, status_code=422)
    except QuotaExceeded as e:
        await ctx.session.rollback()
        return JSONResponse({"detail": "quota_exceeded", "code": e.code}, status_code=409)
    await ctx.session.commit()
    await cache.bump_data_version(ctx.farm_id)
    return result


DEFAULT_PAGE = LIMITS["page_default"]
