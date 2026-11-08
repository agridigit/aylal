"""F3 writes over sync: zone observations (put) and the staff dismissal of a zone (patch). No other write exists.

Same access control as REST, through monitoring.access (visible_parcels): `authorize` runs for the whole batch before
anything is written (non-member -> 404, parcel not visible -> 404, role -> 403). Server-owned fields are ignored; a storage
key or URL makes the operation rejected with the one `invalid_object_ref` error, whatever the cause. Quotas are read under
the farm lock, in the transaction of the batch.
"""
import uuid
from typing import Any

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.access import farm_role
from app.auth.farm_context import NOT_FOUND, FarmContext
from app.db.models import AppliedOp
from app.domain.monitoring_limits import LIMITS
from app.domain.roles import can
from app.monitoring import access, service, uploads
from app.monitoring.schemas import ObservationInput

# Same lock as the REST path: taken before any quota is read.
_FARM_LOCK = "SELECT pg_advisory_xact_lock(hashtextextended(CAST(:farm AS text), 0))"
MONITORING_TABLES = ("zone_observations", "attention_zones")
Result = dict[str, Any]
OBJECT_KEYS = frozenset({"photo_key", "map_key", "raster_key", "label_photo_key", "object_key", "url"})
CLIENT_FIELDS = frozenset({"zone_id", "note", "photo_id"})


async def authorize(session: AsyncSession, user_id: uuid.UUID, ops: list[dict[str, Any]]) -> None:
    for op in ops:
        if op["table"] not in MONITORING_TABLES:
            continue
        farm_id = op.get("farm_id")
        if farm_id is None:
            raise HTTPException(status_code=422, detail="farm_id_required")
        role = await farm_role(session, farm_id, user_id)
        if role is None:
            raise NOT_FOUND
        ctx = FarmContext(farm_id, user_id, role, session)
        if op["table"] == "zone_observations":
            if op["kind"] != "put":
                raise HTTPException(status_code=403, detail="forbidden")  # observations are append-only
            zone = uuid.UUID(str(op["fields"].get("zone_id"))) if _is_uuid(op["fields"].get("zone_id")) else None
            if zone is None:
                continue  # rejected as invalid at apply time (no existence oracle)
            await access.object_access(ctx, "attention_zones", zone, "zone.observe")
        else:
            if op["kind"] != "patch":
                raise HTTPException(status_code=403, detail="forbidden")
            await access.object_access(ctx, "attention_zones", op["record_id"], "zone.dismiss")


def _is_uuid(value: Any) -> bool:
    try:
        uuid.UUID(str(value))
    except ValueError:
        return False
    return True


def _rejected(op_id: uuid.UUID, code: str, field: str | None = None) -> Result:
    return {"op_id": str(op_id), "status": "rejected", "error": {"code": code, **({"field": field} if field else {})}}


async def apply_op(session: AsyncSession, user_id: uuid.UUID, op: dict[str, Any]) -> Result:
    op_id: uuid.UUID = op["op_id"]
    seen = await session.get(AppliedOp, op_id)
    if seen is not None:
        return {**seen.result, "status": "duplicate"}
    async with session.begin_nested():
        result = await _dispatch(session, user_id, op)
    session.add(AppliedOp(op_id=op_id, record_id=op["record_id"], result=result))
    return result


async def _dispatch(session: AsyncSession, user_id: uuid.UUID, op: dict[str, Any]) -> Result:
    op_id, farm_id = op["op_id"], op["farm_id"]
    await session.execute(text(_FARM_LOCK), {"farm": str(farm_id)})
    raw: dict[str, Any] = op["fields"]
    if op["table"] == "zone_observations":  # cheap early refusal under the lock; service.create_observation rechecks every quota
        year = (await session.execute(text("SELECT count(*) FROM zone_observations WHERE farm_id = :f AND created_at >= now() - interval '1 year'"), {"f": farm_id})).scalar_one()
        if year >= LIMITS["observations_per_farm_year"]:
            return _rejected(op_id, "quota_exceeded")
    if op["table"] == "attention_zones":
        if raw.get("status") != "dismissed":
            return _rejected(op_id, "validation", "status")
        role = await farm_role(session, farm_id, user_id)
        if role is None or not can(role, "zone.dismiss"):
            return _rejected(op_id, "forbidden")
        await session.execute(
            text("UPDATE attention_zones SET status = 'dismissed' WHERE id = :i AND farm_id = :f"), {"i": op["record_id"], "f": farm_id}
        )
        return {"op_id": str(op_id), "status": "applied", "server_version": 1}
    if any(raw.get(k) is not None for k in OBJECT_KEYS):
        return _rejected(op_id, "invalid_object_ref")
    zone = raw.get("zone_id")
    if not _is_uuid(zone):
        return _rejected(op_id, "validation", "zone_id")
    ctx = FarmContext(farm_id, user_id, await farm_role(session, farm_id, user_id) or "", session)
    try:
        await access.object_access(ctx, "attention_zones", uuid.UUID(str(zone)), "zone.observe")
        body = ObservationInput.model_validate({"id": str(op["record_id"]), **{k: v for k, v in raw.items() if k in CLIENT_FIELDS - {"zone_id"}}})
        await service.create_observation(session, farm_id, user_id, uuid.UUID(str(zone)), body.id, body.note, body.photo_id)
    except ValidationError as e:
        loc = e.errors()[0]["loc"]
        return _rejected(op_id, "invalid_object_ref") if loc and loc[0] == "photo_id" else _rejected(op_id, "validation", str(loc[0]) if loc else None)
    except uploads.InvalidObjectRef:
        return _rejected(op_id, "invalid_object_ref")
    except service.QuotaExceeded as e:
        return _rejected(op_id, e.code)
    except HTTPException as e:
        return _rejected(op_id, "not_found" if e.status_code == 404 else "forbidden")
    return {"op_id": str(op_id), "status": "applied", "server_version": 1}
