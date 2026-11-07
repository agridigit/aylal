"""F2 writes over sync (parcels, seasons, field_blocks, crops, field_commands).

Same access control as REST: `authorize` runs for the whole batch before anything is written
(non-member -> 404, worker or insufficient role -> 403, object of another farm, deleted farm or
archived field -> 404). Server-owned columns are never taken from the client: only the whitelisted
attributes of app.fields.service are read from `fields`.
"""
import datetime as dt
import json
import uuid
from typing import Any

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.access import farm_role
from app.auth.farm_context import NOT_FOUND
from app.db.models import AppliedOp
from app.domain.conflict import resolve_field_conflicts
from app.domain.roles import can
from app.fields import service
from app.fields.service import FieldError

F2_TABLES = ("parcels", "seasons", "field_blocks", "crops", "field_commands")
Result = dict[str, Any]
_PASSTHROUGH_CODES = {"outside_morocco", "area_too_large", "field_limit_reached"}
_FIELD_ATTRS = ("name", "geometry", "irrigation", "greenhouse", "soil", "area_declared_ha", "gps_accuracy_m", "source")
_ACTION = {
    "parcels": "field.update", "seasons": "season.update", "field_blocks": "field.split",
    "crops": "crop.create_custom", "field_commands": "field.merge",
}
# table -> SQL returning (farm_id, parent field archived?) of an existing record
_LOOKUP = {
    "parcels": "SELECT farm_id, archived_at IS NOT NULL AS archived, id AS field_id FROM parcels WHERE id = :i",
    "seasons": "SELECT s.farm_id, p.archived_at IS NOT NULL AS archived, s.field_id FROM seasons s JOIN parcels p ON p.id = s.field_id WHERE s.id = :i",
    "field_blocks": "SELECT b.farm_id, p.archived_at IS NOT NULL AS archived, b.field_id FROM field_blocks b JOIN parcels p ON p.id = b.field_id WHERE b.id = :i",
    "crops": "SELECT farm_id, false AS archived, NULL AS field_id FROM crops WHERE id = :i",
    "field_commands": "SELECT farm_id, false AS archived, NULL AS field_id FROM field_commands WHERE id = :i",
}


async def _existing(session: AsyncSession, table: str, record_id: uuid.UUID) -> dict[str, Any] | None:
    row = (await session.execute(text(_LOOKUP[table]), {"i": record_id})).mappings().first()
    return dict(row) if row else None


def _uuid(value: Any) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value))
    except ValueError:
        return None


async def authorize(session: AsyncSession, user_id: uuid.UUID, ops: list[dict[str, Any]]) -> None:
    created_farms: set[uuid.UUID] = set()  # farms created earlier in this batch by this user
    created_fields: set[tuple[uuid.UUID, uuid.UUID]] = set()
    for op in ops:
        farm_id = op.get("farm_id")
        if op["table"] == "farms" and op["kind"] == "put" and op["record_id"] == farm_id:
            created_farms.add(farm_id)
        if op["table"] not in F2_TABLES:
            continue
        if farm_id is None:
            raise HTTPException(status_code=422, detail="farm_id_required")
        role = await farm_role(session, farm_id, user_id)
        if role is None:
            if farm_id in created_farms and (await session.execute(text("SELECT 1 FROM farms WHERE id = :i"), {"i": farm_id})).first() is None:
                role = "owner"
            else:
                raise NOT_FOUND
        if not can(role, _ACTION[op["table"]]):
            raise HTTPException(status_code=403, detail="forbidden")
        existing = await _existing(session, op["table"], op["record_id"])
        if existing is not None and (existing["farm_id"] != farm_id or existing["archived"]):
            raise NOT_FOUND  # another farm's object, or a write under an archived field
        if existing is None and op["table"] == "parcels":
            created_fields.add((farm_id, op["record_id"]))
        parent = _uuid(op["fields"].get("field_id")) if existing is None and op["table"] in ("seasons", "field_blocks") else None
        if parent is not None and (farm_id, parent) not in created_fields:
            found = (await session.execute(
                text("SELECT 1 FROM parcels WHERE id = :i AND farm_id = :f AND archived_at IS NULL"), {"i": parent, "f": farm_id}
            )).first()
            if found is None:
                raise NOT_FOUND


def _rejected(op_id: uuid.UUID, code: str, field: str | None = None) -> Result:
    return {"op_id": str(op_id), "status": "rejected", "error": {"code": code, **({"field": field} if field else {})}}


async def apply_op(session: AsyncSession, user_id: uuid.UUID, op: dict[str, Any]) -> Result:
    op_id: uuid.UUID = op["op_id"]
    seen = await session.get(AppliedOp, op_id)
    if seen is not None:
        return {**seen.result, "status": "duplicate"}
    try:
        async with session.begin_nested():  # an op that fails leaves no partial write
            result = await _dispatch(session, user_id, op)
    except FieldError as e:
        result = _rejected(op_id, "not_found" if e.status == 404 else "forbidden" if e.status == 403 else "conflict" if e.status == 409 else e.code if e.code in _PASSTHROUGH_CODES else "validation", e.field)
    session.add(AppliedOp(op_id=op_id, record_id=op["record_id"], result=result))
    return result


async def _dispatch(session: AsyncSession, user_id: uuid.UUID, op: dict[str, Any]) -> Result:
    table, kind, rid, farm_id, data = op["table"], op["kind"], op["record_id"], op["farm_id"], op["fields"]
    existing = await _existing(session, table, rid)
    if kind == "patch" and existing is None:
        raise FieldError(404, "not_found")
    ok: Result = {"op_id": str(op["op_id"]), "status": "applied"}
    field_id = existing["field_id"] if existing else _uuid(data.get("field_id"))
    if table == "parcels":
        if kind == "delete":
            await service.archive_field(session, farm_id, rid)
        elif existing is None:
            await service.create_field(session, farm_id, user_id, data, rid)
        else:
            return await _update_field_with_conflicts(session, op, ok)
    elif table == "seasons":
        if kind == "delete":
            raise FieldError(403, "seasons_are_never_deleted")
        if field_id is None:
            raise FieldError(422, "validation", "field_id")
        if existing is None:
            await service.create_season(session, farm_id, field_id, data, rid)
        else:
            await service.update_season(session, farm_id, field_id, rid, data)
    elif table == "field_blocks":
        if field_id is None:
            raise FieldError(422, "validation", "field_id")
        if kind == "delete":
            await service.delete_block(session, farm_id, field_id, rid)
        elif existing is None:
            await service.create_block(session, farm_id, field_id, data, rid)
        else:
            await service.update_block(session, farm_id, field_id, rid, data)
    elif table == "crops":
        if kind == "delete":
            await service.archive_crop(session, farm_id, rid)
        elif existing is None:
            await service.create_crop(session, farm_id, user_id, data, rid)
        else:
            await service.update_crop(session, farm_id, rid, data)
    else:
        return await _command(session, user_id, op, existing, ok)
    return ok


async def _update_field_with_conflicts(session: AsyncSession, op: dict[str, Any], ok: Result) -> Result:
    """Field-by-field merge: a contested field goes to the op arriving last, the loser is logged."""
    farm_id, rid, data = op["farm_id"], op["record_id"], op["fields"]
    current = await service.get_field(session, farm_id, rid)
    versions = (await session.execute(
        text("SELECT field_versions FROM parcels WHERE id = :i AND farm_id = :f"), {"i": rid, "f": farm_id}
    )).scalar_one()
    changes = {k: data[k] for k in _FIELD_ATTRS if k in data}
    resolved = resolve_field_conflicts(
        {"server_version": current["server_version"], "fields": current, "field_versions": dict(versions or {})},
        {"changes": changes, "base_version": op["base_version"], "author_id": op["author_id"]},
    )
    await service.update_field(session, farm_id, rid, data)
    await session.execute(
        text("UPDATE parcels SET field_versions = CAST(:v AS jsonb) WHERE id = :i AND farm_id = :f"),
        {"v": json.dumps(resolved["field_versions"]), "i": rid, "f": farm_id},
    )
    for c in resolved["conflicts"]:
        await session.execute(
            text(
                "INSERT INTO sync_conflicts (id, farm_id, record_id, field, discarded_value, kept_value,"
                " discarded_by, base_version, server_version)"
                " VALUES (:id, :f, :r, :field, CAST(:d AS jsonb), CAST(:k AS jsonb), :by, :bv, :sv)"
            ),
            {"id": uuid.uuid4(), "f": farm_id, "r": rid, "field": c["field"],
             "d": json.dumps(c["discarded_value"], default=str), "k": json.dumps(c["kept_value"], default=str),
             "by": c["discarded_by"], "bv": c["base_version"], "sv": c["server_version"]},
        )
    return {**ok, "status": "conflict_logged"} if resolved["conflicts"] else ok


async def _command(session: AsyncSession, user_id: uuid.UUID, op: dict[str, Any], existing: Any, ok: Result) -> Result:
    data = op["fields"]
    if op["kind"] != "put" or existing is not None:
        raise FieldError(409, "commands_are_insert_only")
    payload = data.get("payload")
    if data.get("kind") != "merge" or not isinstance(payload, dict):
        raise FieldError(422, "validation", "kind")
    failure: FieldError | None = None
    try:
        async with session.begin_nested():
            await service.merge_fields(session, op["farm_id"], payload.get("survivor_id"), payload.get("merged_ids"))
    except FieldError as e:
        failure = e
    outcome = {"ok": True} if failure is None else {"error": {"code": failure.code}}
    await session.execute(
        text(
            "INSERT INTO field_commands (id, farm_id, kind, payload, created_by, applied_at, result)"
            " VALUES (:i, :f, 'merge', CAST(:p AS jsonb), :u, :a, CAST(:r AS jsonb))"
        ),
        {"i": op["record_id"], "f": op["farm_id"], "p": json.dumps(payload), "u": user_id,
         "a": dt.datetime.now(dt.UTC), "r": json.dumps(outcome)},
    )
    if failure is not None:
        return _rejected(op["op_id"], failure.code if failure.status != 404 else "not_found", failure.field)
    return ok
