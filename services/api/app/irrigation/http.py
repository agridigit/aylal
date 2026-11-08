"""HTTP mapping of the F4 refusals (shared by the five routers)."""
from collections.abc import Awaitable, Callable, Coroutine
from typing import Any

from fastapi import Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

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


class NamedFieldRoute(APIRoute):
    """Body validation failures answer the contract `Invalid` shape: `{detail: "validation", field, code}` (the first offending field)."""

    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        original = super().get_route_handler()

        async def handler(request: Request) -> Response:
            try:
                return await original(request)
            except RequestValidationError as e:
                first = e.errors()[0]
                loc = [p for p in first["loc"] if p != "body"]
                code = str(first["msg"]).removeprefix("Value error, ") if first["type"] == "value_error" else first["type"]
                return JSONResponse({"detail": "validation", "field": str(loc[0]) if loc else None, "code": code}, status_code=422)

        return handler
