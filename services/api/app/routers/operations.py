"""Operations journal routes (F6). Every route goes through farm_context / require(action)."""
import base64
import datetime as dt
import uuid
from typing import Any, Literal

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.auth.farm_context import NOT_FOUND, FarmContext, require
from app.auth.rate_limit import check_rate_limit
from app.config import get_settings
from app.domain.harvest_date import earliest_harvest as earliest_harvest_of
from app.domain.operation_limits import LIMITS
from app.operations import label, service
from app.operations.access import STAFF
from app.operations.schemas import OperationInput, OperationPatch, ParseRequest, RescheduleRequest

router = APIRouter(prefix="/farms/{farm_id}")
_LIMIT = Query(default=LIMITS["page_default"], ge=1, le=LIMITS["page_limit"])
_REQUIRE_OPERATION_CANCEL = require("operation.cancel")
_PHOTO = File(...)
_REQUIRE_OPERATION_CORRECT = require("operation.correct")
_REQUIRE_OPERATION_CREATE = require("operation.create")
_REQUIRE_OPERATION_MARK_DONE = require("operation.mark_done")
_REQUIRE_OPERATION_READ = require("operation.read")
_REQUIRE_OPERATION_RESCHEDULE = require("operation.reschedule")
_REQUIRE_OPERATION_VALIDATE = require("operation.validate")


def _http(e: service.OperationError) -> HTTPException:
    if e.status == 404:
        return NOT_FOUND
    detail: dict[str, Any] = {"code": e.code}
    if e.field:
        detail["field"] = e.field
    return HTTPException(status_code=e.status, detail=detail)


def _cursor(value: str | None) -> tuple[dt.date, uuid.UUID] | None:
    if not value:
        return None
    try:
        day, ident = base64.urlsafe_b64decode(value.encode()).decode().split("|")
        return dt.date.fromisoformat(day), uuid.UUID(ident)
    except ValueError as e:
        raise HTTPException(status_code=422, detail={"code": "invalid_cursor"}) from e


@router.get("/operations")
async def list_operations(
    limit: int = _LIMIT,
    cursor: str | None = None, parcel_id: uuid.UUID | None = None, type: str | None = None,
    status: Literal["planned", "done", "pending_validation", "validated", "cancelled"] | None = None,
    ctx: FarmContext = Depends(_REQUIRE_OPERATION_READ),
) -> dict[str, Any]:
    items, more = await service.list_page(
        ctx.session, ctx.farm_id, ctx.user_id, ctx.role, limit=limit, after=_cursor(cursor), parcel_id=parcel_id,
        type_=type, status=status,
    )
    last = items[-1] if items else None
    next_cursor = (
        base64.urlsafe_b64encode(f"{last['performed_on']}|{last['id']}".encode()).decode() if more and last else None
    )
    return {"items": items, "next_cursor": next_cursor}


@router.post("/operations", status_code=201)
async def create_operation(
    body: OperationInput, response: Response, ctx: FarmContext = Depends(_REQUIRE_OPERATION_CREATE)
) -> dict[str, Any]:
    try:
        out, created = await service.create_operation(
            ctx.session, ctx.farm_id, ctx.user_id, ctx.role, body.model_dump(mode="json", exclude={"status"})
        )
    except service.OperationError as e:
        raise _http(e) from e
    await ctx.session.commit()
    if not created:
        response.status_code = 200
    return out


@router.post("/operations/check")
async def check_operation(body: OperationInput, ctx: FarmContext = Depends(_REQUIRE_OPERATION_CREATE)) -> dict[str, Any]:
    try:
        return await service.check(ctx.session, ctx.farm_id, ctx.user_id, ctx.role, body.model_dump(mode="json", exclude={"status"}))
    except service.OperationError as e:
        raise _http(e) from e


@router.post("/operations/parse", response_model=None)
async def parse_operation(body: ParseRequest, ctx: FarmContext = Depends(_REQUIRE_OPERATION_CREATE)) -> Any:
    await check_rate_limit(f"rl:parse:{ctx.user_id}", 60)
    if not get_settings().nlu_url:
        return JSONResponse(status_code=503, content={"code": "parse_unavailable"})
    return JSONResponse(status_code=503, content={"code": "parse_unavailable"})  # the NLU port is wired with the dictation story


@router.post("/operations/label", response_model=None)
async def recognise_label(
    photo: UploadFile = _PHOTO, ctx: FarmContext = Depends(_REQUIRE_OPERATION_CREATE),
    recognizer: label.LabelRecognizer = Depends(label.get_recognizer),
) -> Any:
    await check_rate_limit(f"rl:label:{ctx.user_id}", 20)
    data = await photo.read(LIMITS["label_bytes"] + 1)
    if len(data) > LIMITS["label_bytes"]:
        raise HTTPException(status_code=413, detail={"code": "payload_too_large"})
    if label.sniff(data) is None:
        raise HTTPException(status_code=422, detail={"code": "invalid_image"})
    label_id = await label.register_upload(ctx.session, ctx.farm_id, ctx.user_id, len(data))
    await ctx.session.commit()
    try:
        raw = await recognizer.recognize(data)
    except (label.RecognizerUnavailable, TimeoutError, OSError):
        return JSONResponse(status_code=503, content={"code": "label_unavailable", "label_photo_id": str(label_id), "candidates": []})
    return {"label_photo_id": str(label_id), "candidates": await label.catalogue_candidates(ctx.session, raw)}


@router.get("/operations/{operation_id}")
async def get_operation(operation_id: uuid.UUID, ctx: FarmContext = Depends(_REQUIRE_OPERATION_READ)) -> dict[str, Any]:
    try:
        return await service.detail(ctx.session, ctx.farm_id, operation_id, ctx.user_id, ctx.role)
    except service.OperationError as e:
        raise _http(e) from e


@router.patch("/operations/{operation_id}")
async def correct_operation(
    operation_id: uuid.UUID, body: OperationPatch, ctx: FarmContext = Depends(_REQUIRE_OPERATION_CORRECT)
) -> dict[str, Any]:
    try:
        out = await service.correct(
            ctx.session, ctx.farm_id, operation_id, ctx.user_id, ctx.role,
            body.model_dump(mode="json", exclude_unset=True, exclude={"status"}),
        )
    except service.OperationError as e:
        raise _http(e) from e
    await ctx.session.commit()
    return out


async def _act(action: str, operation_id: uuid.UUID, ctx: FarmContext) -> dict[str, Any]:
    try:
        out = await service.transition(ctx.session, ctx.farm_id, operation_id, ctx.user_id, ctx.role, action)
    except service.OperationError as e:
        raise _http(e) from e
    await ctx.session.commit()
    return out


@router.post("/operations/{operation_id}/done")
async def mark_done(operation_id: uuid.UUID, ctx: FarmContext = Depends(_REQUIRE_OPERATION_MARK_DONE)) -> dict[str, Any]:
    return await _act("mark_done", operation_id, ctx)


@router.post("/operations/{operation_id}/cancel")
async def cancel(operation_id: uuid.UUID, ctx: FarmContext = Depends(_REQUIRE_OPERATION_CANCEL)) -> dict[str, Any]:
    return await _act("cancel", operation_id, ctx)


@router.post("/operations/{operation_id}/reschedule")
async def reschedule(
    operation_id: uuid.UUID, body: RescheduleRequest, ctx: FarmContext = Depends(_REQUIRE_OPERATION_RESCHEDULE)
) -> dict[str, Any]:
    try:
        out = await service.reschedule(ctx.session, ctx.farm_id, operation_id, ctx.user_id, ctx.role, body.performed_on)
    except service.OperationError as e:
        raise _http(e) from e
    await ctx.session.commit()
    return out


@router.post("/operations/{operation_id}/validate")
async def validate(operation_id: uuid.UUID, ctx: FarmContext = Depends(_REQUIRE_OPERATION_VALIDATE)) -> dict[str, Any]:
    return await _act("validate", operation_id, ctx)


@router.get("/operations/{operation_id}/corrections")
async def list_corrections(operation_id: uuid.UUID, ctx: FarmContext = Depends(_REQUIRE_OPERATION_CORRECT)) -> dict[str, Any]:
    try:
        return {"items": await service.corrections(ctx.session, ctx.farm_id, operation_id)}
    except service.OperationError as e:
        raise _http(e) from e


async def _harvest_scope(field_id: uuid.UUID, ctx: FarmContext = Depends(_REQUIRE_OPERATION_READ)) -> FarmContext:
    """Staff: any parcel of the farm (archived too); worker: assigned and not archived, else 404."""
    query = "SELECT 1 FROM parcels p WHERE p.id = :p AND p.farm_id = :f"
    if ctx.role not in STAFF:
        query += (
            " AND p.archived_at IS NULL AND EXISTS (SELECT 1 FROM worker_parcels w WHERE w.farm_id = p.farm_id"
            " AND w.parcel_id = p.id AND w.user_id = :u)"
        )
    if (await ctx.session.execute(text(query), {"p": field_id, "f": ctx.farm_id, "u": ctx.user_id})).first() is None:
        raise NOT_FOUND
    return ctx


@router.get("/fields/{field_id}/earliest-harvest")
async def earliest_harvest(field_id: uuid.UUID, ctx: FarmContext = Depends(_harvest_scope)) -> dict[str, Any]:
    """Earliest harvest date: the latest `performed_on + dar_days` of the current registry entries of the parcel."""
    rows = (
        await ctx.session.execute(
            text(
                "SELECT id, entry_kind, supersedes_id, performed_on, dar_days, product_name FROM registry_current"
                " WHERE farm_id = :f AND parcel_id = :p"
            ),
            {"f": ctx.farm_id, "p": field_id},
        )
    ).mappings().all()
    return earliest_harvest_of([dict(r) for r in rows], dt.date.today())
