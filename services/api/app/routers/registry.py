"""Regulatory registry routes (F6): read the current view, request and follow an export. Never a write route."""
import base64
import datetime as dt
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import text

from app.auth.farm_context import NOT_FOUND, FarmContext, require
from app.domain.operation_limits import LIMITS
from app.operations import exports, queue, registry
from app.operations.schemas import RegistryExportRequest
from app.operations.service import OperationError
from app.operations.storage import ObjectStorage, get_storage

router = APIRouter(prefix="/farms/{farm_id}/registry")
_FROM = Query(default=None, alias="from")
_LIMIT = Query(default=LIMITS["page_default"], ge=1, le=LIMITS["page_limit"])
_REQUIRE_REGISTRY_EXPORT = require("registry.export")
_REQUIRE_REGISTRY_READ = require("registry.read")


def _http(e: OperationError) -> HTTPException:
    if e.status == 404:
        return NOT_FOUND
    return HTTPException(status_code=e.status, detail={"code": e.code, **({"field": e.field} if e.field else {})})


@router.get("")
async def list_registry(
    parcel_id: uuid.UUID | None = None,
    from_: dt.date | None = _FROM,
    to: dt.date | None = None,
    limit: int = _LIMIT,
    cursor: str | None = None,
    ctx: FarmContext = Depends(_REQUIRE_REGISTRY_READ),
) -> dict[str, Any]:
    after = None
    if cursor:
        try:
            day, ident = base64.urlsafe_b64decode(cursor.encode()).decode().split("|")
            after = (dt.date.fromisoformat(day), uuid.UUID(ident))
        except ValueError as e:
            raise HTTPException(status_code=422, detail={"code": "invalid_cursor"}) from e
    items, more = await registry.list_entries(
        ctx.session, ctx.farm_id, parcel_id=parcel_id, start=from_, end=to, limit=limit, after=after
    )
    last = items[-1] if items else None
    nxt = base64.urlsafe_b64encode(f"{last['performed_on']}|{last['id']}".encode()).decode() if more and last else None
    return {"items": items, "next_cursor": nxt}


@router.post("/exports", status_code=202)
async def request_export(
    body: RegistryExportRequest, response: Response, ctx: FarmContext = Depends(_REQUIRE_REGISTRY_EXPORT)
) -> dict[str, Any]:
    try:
        out = await exports.request_export(ctx.session, ctx.farm_id, ctx.user_id, body.model_dump())
    except OperationError as e:
        raise _http(e) from e
    await ctx.session.commit()
    try:
        await queue.enqueue_registry_export(out["id"])
    except Exception as e:  # the job would stay queued and block the farm's slot: fail it and free the slot
        await ctx.session.execute(text("UPDATE export_jobs SET state = 'failed' WHERE id = :i"), {"i": out["id"]})
        await ctx.session.commit()
        raise HTTPException(status_code=503, detail={"code": "export_unavailable"}) from e
    return out


@router.get("/exports/{job_id}")
async def export_status(
    job_id: uuid.UUID, response: Response, ctx: FarmContext = Depends(_REQUIRE_REGISTRY_EXPORT),
    storage: ObjectStorage = Depends(get_storage),
) -> dict[str, Any]:
    response.headers["Cache-Control"] = "no-store"
    try:
        return await exports.job_status(ctx.session, ctx.farm_id, job_id, ctx.user_id, storage)
    except OperationError as e:
        raise _http(e) from e
