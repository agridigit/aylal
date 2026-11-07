"""Farm-administration writes over sync (farms, farm_members, worker_parcels, invitations).

Same authorisation as REST (F1 guard-rail 3): `authorize` runs for the whole batch before anything
is written. Non-member -> 404, insufficient role -> 403, payload errors -> 422 only afterwards.
The creation of one's own farm (farm_id == record_id, farm unknown) is the only open write.
"""
import datetime as dt
import uuid
from typing import Any

from fastapi import HTTPException
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.access import farm_role
from app.auth.farm_context import NOT_FOUND
from app.db.models import AppliedOp, Farm, FarmMember, Invitation, Parcel, WorkerParcel
from app.domain.phone import normalize_phone
from app.domain.roles import can
from app.domain.validation import validate

ADMIN_TABLES = ("farms", "farm_members", "worker_parcels", "invitations")
Result = dict[str, Any]


def _action(table: str, kind: str) -> str:
    if table == "farms":
        return "farm.delete" if kind == "delete" else "farm.update"
    if table == "farm_members":
        return "member.remove" if kind == "delete" else "member.role_change"
    if table == "worker_parcels":
        return "parcels.assign"
    return "member.invite"


def _is_creation(op: dict[str, Any]) -> bool:
    return op["table"] == "farms" and op["kind"] == "put" and op["record_id"] == op["farm_id"]


async def authorize(session: AsyncSession, user_id: uuid.UUID, ops: list[dict[str, Any]]) -> None:
    for op in ops:
        if op["table"] not in ADMIN_TABLES:
            continue
        farm_id = op.get("farm_id")
        if farm_id is None:
            raise HTTPException(status_code=422, detail="farm_id_required")
        role = await farm_role(session, farm_id, user_id)
        if role is None:
            if _is_creation(op) and await session.get(Farm, farm_id) is None:
                continue
            raise NOT_FOUND
        if not can(role, _action(op["table"], op["kind"])):
            raise HTTPException(status_code=403, detail="forbidden")


def _rejected(op_id: uuid.UUID, code: str, field: str | None = None) -> Result:
    error = {"code": code, **({"field": field} if field else {})}
    return {"op_id": str(op_id), "status": "rejected", "error": error}


async def apply_admin_op(session: AsyncSession, user_id: uuid.UUID, op: dict[str, Any]) -> Result:
    from app.routers.farms import create_owned_farm  # avoid an import cycle at module load

    op_id = op["op_id"]
    seen = await session.get(AppliedOp, op_id)
    if seen is not None:
        return {**seen.result, "status": "duplicate"}
    farm_id: uuid.UUID = op["farm_id"]
    fields: dict[str, Any] = op["fields"]
    table, kind = op["table"], op["kind"]
    if table == "farms":
        result = await _farm(session, user_id, op, farm_id, fields, create_owned_farm)
    elif table == "farm_members":
        result = await _member(session, op_id, farm_id, fields, kind)
    elif table == "worker_parcels":
        result = await _worker_parcel(session, op_id, farm_id, fields, kind)
    else:
        result = await _invitation(session, user_id, op, farm_id, fields)
    session.add(AppliedOp(op_id=op_id, record_id=op["record_id"], result=result))
    return result


async def _farm(session: Any, user_id: Any, op: Any, farm_id: Any, fields: Any, create: Any) -> Result:
    op_id = op["op_id"]
    farm = await session.get(Farm, farm_id)
    if farm is None:  # creation by the future owner
        verdict = validate("farm", fields)
        if not verdict["valid"]:
            return _rejected(op_id, "validation", verdict["errors"][0]["field"])
        await create(session, farm_id, user_id, fields)
    elif op["kind"] == "delete":
        farm.deleted_at = dt.datetime.now(dt.UTC)
    else:
        name = fields.get("name", farm.name)
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 120:
            return _rejected(op_id, "validation", "name")
        farm.name = name.strip()
        if fields.get("area_ha") is not None:
            farm.area_ha = fields["area_ha"]
    return {"op_id": str(op_id), "status": "applied"}


async def _member(session: AsyncSession, op_id: Any, farm_id: Any, fields: Any, kind: str) -> Result:
    try:
        target = uuid.UUID(str(fields.get("user_id")))
    except ValueError:
        raise HTTPException(status_code=422, detail="user_id_required") from None
    role = fields.get("role")
    if kind != "delete" and role not in ("manager", "worker"):
        raise HTTPException(status_code=422, detail="role_invalid")
    member = (
        await session.execute(
            select(FarmMember).where(
                FarmMember.farm_id == farm_id,
                FarmMember.user_id == target,
                FarmMember.removed_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if member is None:
        return _rejected(op_id, "not_found")
    if member.role == "owner":
        return _rejected(op_id, "forbidden")
    if kind == "delete":
        member.removed_at = dt.datetime.now(dt.UTC)
    else:
        member.role = role
    if kind == "delete" or role != "worker":
        await session.execute(
            delete(WorkerParcel).where(WorkerParcel.farm_id == farm_id, WorkerParcel.user_id == target)
        )
    return {"op_id": str(op_id), "status": "applied"}


async def _worker_parcel(
    session: AsyncSession, op_id: Any, farm_id: Any, fields: Any, kind: str
) -> Result:
    try:
        target = uuid.UUID(str(fields.get("user_id")))
        parcel_id = uuid.UUID(str(fields.get("parcel_id")))
    except ValueError:
        raise HTTPException(status_code=422, detail="user_id_parcel_id_required") from None
    if kind == "delete":
        await session.execute(
            delete(WorkerParcel).where(
                WorkerParcel.farm_id == farm_id,
                WorkerParcel.user_id == target,
                WorkerParcel.parcel_id == parcel_id,
            )
        )
        return {"op_id": str(op_id), "status": "applied"}
    member = (
        await session.execute(
            select(FarmMember.role).where(
                FarmMember.farm_id == farm_id,
                FarmMember.user_id == target,
                FarmMember.removed_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    parcel = (
        await session.execute(select(Parcel.id).where(Parcel.id == parcel_id, Parcel.farm_id == farm_id))
    ).scalar_one_or_none()
    if member != "worker" or parcel is None:
        return _rejected(op_id, "not_found")
    existing = await session.get(WorkerParcel, (farm_id, target, parcel_id))
    if existing is None:
        session.add(WorkerParcel(farm_id=farm_id, user_id=target, parcel_id=parcel_id))
    return {"op_id": str(op_id), "status": "applied"}


async def _invitation(
    session: AsyncSession, user_id: Any, op: Any, farm_id: Any, fields: Any
) -> Result:
    op_id = op["op_id"]
    if op["kind"] == "delete":
        await session.execute(
            update(Invitation)
            .where(Invitation.id == op["record_id"], Invitation.farm_id == farm_id)
            .values(status="cancelled")
        )
        return {"op_id": str(op_id), "status": "applied"}
    phone = normalize_phone(str(fields.get("phone_e164", "")))
    role = fields.get("role")
    if phone is None:
        return _rejected(op_id, "validation", "phone_e164")
    if role not in ("manager", "worker"):
        return _rejected(op_id, "validation", "role")
    pending = (
        await session.execute(
            select(Invitation.id).where(
                Invitation.farm_id == farm_id,
                Invitation.phone_e164 == phone,
                Invitation.status == "pending",
            )
        )
    ).first()
    if pending is not None:
        return _rejected(op_id, "conflict", "phone_e164")
    session.add(
        Invitation(
            id=op["record_id"], farm_id=farm_id, phone_e164=phone, role=role, status="pending",
            invited_by=user_id, expires_at=dt.datetime.now(dt.UTC) + dt.timedelta(days=30),
        )
    )
    return {"op_id": str(op_id), "status": "applied"}
