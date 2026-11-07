"""F6 writes over sync: `operations` (put = create, patch = correction). Never a physical delete.

Same access control as REST (G1): `authorize` runs for the whole batch before anything is written (non-member ->
404, role -> 403, parcel of another farm, archived, or not assigned to a worker -> 404). Server-owned fields sent by
a client are ignored; a storage key or URL is never read: it makes the operation rejected (`invalid_object_ref`).
Each operation runs in a savepoint, so a rejected one leaves nothing behind.
"""
import uuid
from typing import Any

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.access import farm_role
from app.auth.farm_context import NOT_FOUND
from app.db.models import AppliedOp
from app.domain.operation_limits import LIMITS
from app.domain.roles import can
from app.operations import access, service
from app.operations.schemas import OperationInput, OperationPatch

OPERATION_TABLES = ("operations",)
Result = dict[str, Any]
SERVER_OWNED = frozenset({
    "id", "farm_id", "status", "author_id", "warnings", "validated_by", "validated_at", "registry_entry_id",
    "parcel_archived_at", "done_at", "created_at", "updated_at", "server_version", "field_versions",
})
OBJECT_KEYS = frozenset({"label_photo_key", "file_keys", "file_key", "object_key", "url"})


def _uuids(value: Any) -> list[uuid.UUID] | None:
    if not isinstance(value, list) or len(value) > LIMITS["parcels"]:
        return None
    try:
        return list(dict.fromkeys(uuid.UUID(str(v)) for v in value))
    except ValueError:
        return None


async def authorize(session: AsyncSession, user_id: uuid.UUID, ops: list[dict[str, Any]]) -> None:
    created = {(o.get("farm_id"), o["record_id"]) for o in ops if o["table"] == "parcels" and o["kind"] == "put"}
    for op in ops:
        if op["table"] not in OPERATION_TABLES:
            continue
        farm_id = op.get("farm_id")
        if farm_id is None:
            raise HTTPException(status_code=422, detail="farm_id_required")
        role = await farm_role(session, farm_id, user_id)
        if role is None:
            raise NOT_FOUND
        if op["kind"] == "delete" or not can(role, "operation.create" if op["kind"] == "put" else "operation.correct"):
            raise HTTPException(status_code=403, detail="forbidden")
        existing = (await session.execute(text("SELECT farm_id FROM operations WHERE id = :i"), {"i": op["record_id"]})).first()
        if existing is not None and existing[0] != farm_id:
            raise NOT_FOUND
        if op["kind"] == "patch" and existing is None:
            raise NOT_FOUND
        if existing is not None and role not in access.STAFF and not await access.can_see(session, farm_id, op["record_id"], user_id, role):
            raise NOT_FOUND
        ids = _uuids(op["fields"].get("parcel_ids")) if op["kind"] == "put" and existing is None else None
        if ids:
            pending = [p for p in ids if not (role in access.STAFF and (farm_id, p) in created)]
            if len(await access.usable_parcels(session, farm_id, user_id, role, pending)) != len(pending):
                raise NOT_FOUND


def _rejected(op_id: uuid.UUID, code: str, field: str | None = None) -> Result:
    return {"op_id": str(op_id), "status": "rejected", "error": {"code": code, **({"field": field} if field else {})}}


def _failure(op_id: uuid.UUID, e: service.OperationError) -> Result:
    code = {404: "not_found", 403: "forbidden", 409: "conflict"}.get(e.status, e.code)
    return _rejected(op_id, code, e.field)


def _fields(raw: dict[str, Any]) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    for key, value in raw.items():
        if key in OBJECT_KEYS:
            if value is not None:
                raise service.OperationError(422, "invalid_object_ref")
        elif key not in SERVER_OWNED:
            fields[key] = value
    return fields


def _model(cls: Any, fields: dict[str, Any]) -> Any:
    try:
        return cls.model_validate(fields)
    except ValidationError as e:
        loc = e.errors()[0]["loc"]
        field = str(loc[0]) if loc else None
        raise service.OperationError(422, "invalid_object_ref" if field == "label_photo_id" else "validation", field) from e


async def apply_op(session: AsyncSession, user_id: uuid.UUID, op: dict[str, Any]) -> Result:
    op_id: uuid.UUID = op["op_id"]
    seen = await session.get(AppliedOp, op_id)
    if seen is not None:
        return {**seen.result, "status": "duplicate"}
    try:
        async with session.begin_nested():
            result = await _dispatch(session, user_id, op)
    except service.OperationError as e:
        result = _failure(op_id, e)
    session.add(AppliedOp(op_id=op_id, record_id=op["record_id"], result=result))
    return result


async def _dispatch(session: AsyncSession, user_id: uuid.UUID, op: dict[str, Any]) -> Result:
    farm_id, record_id = op["farm_id"], op["record_id"]
    role = await farm_role(session, farm_id, user_id)
    if role is None:
        raise service.OperationError(404, "not_found")
    fields = _fields(op["fields"])
    if op["kind"] == "put":
        body = _model(OperationInput, {**fields, "id": str(record_id)})
        out, _ = await service.create_operation(
            session, farm_id, user_id, role, body.model_dump(mode="json", exclude={"status"})
        )
    else:
        patch = _model(OperationPatch, fields)
        out = await service.correct(
            session, farm_id, record_id, user_id, role, patch.model_dump(mode="json", exclude_unset=True, exclude={"status"}),
            base_version=op.get("base_version"),
        )
    return {"op_id": str(op["op_id"]), "status": "applied", "server_version": out["server_version"]}
