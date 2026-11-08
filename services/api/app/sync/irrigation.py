"""F4 writes over sync: irrigation systems (put/patch), irrigation events (put; patch = cancel) and water analyses (put).

Same access control as REST, through irrigation.access (visible_parcels): `authorize` runs for the whole batch before anything is
written (non-member -> 404, parcel not visible -> 404, role -> 403). Server-owned fields are never read: a body that names one is
rejected, and a storage key or URL is rejected as `invalid_object_ref`. Quotas are counted under the farm lock, in the batch
transaction. There is no delete and no table of derived data (plans, balance) is writable.
"""
import datetime as dt
import uuid
from typing import Any

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.access import farm_role
from app.auth.farm_context import NOT_FOUND, FarmContext
from app.db.models import AppliedOp
from app.domain.irrigation_limits import LIMITS
from app.domain.roles import can
from app.irrigation import cache, service
from app.irrigation.access import parcel_readable
from app.irrigation.schemas import IrrigationEventInput, IrrigationSystemInput, WaterAnalysisInput

# Same lock as the REST path: taken before any quota is read.
_FARM_LOCK = "SELECT pg_advisory_xact_lock(hashtextextended(CAST(:farm AS text), 0))"
IRRIGATION_TABLES = ("irrigation_systems", "irrigation_events", "water_analyses")
Result = dict[str, Any]


def _uuid(value: Any) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value))
    except ValueError:
        return None


def _date(value: Any) -> dt.date | None:
    try:
        return dt.date.fromisoformat(str(value))
    except ValueError:
        return None


def _forbidden() -> HTTPException:
    return HTTPException(status_code=403, detail="forbidden")


async def authorize(session: AsyncSession, user_id: uuid.UUID, ops: list[dict[str, Any]]) -> None:
    for op in ops:
        table = op["table"]
        if table not in IRRIGATION_TABLES:
            continue
        farm_id = op.get("farm_id")
        if farm_id is None:
            raise HTTPException(status_code=422, detail="farm_id_required")
        role = await farm_role(session, farm_id, user_id)
        if role is None:
            raise NOT_FOUND
        ctx = FarmContext(farm_id, user_id, role, session)
        if op["kind"] == "delete" or (table == "water_analyses" and op["kind"] != "put"):
            raise _forbidden()  # nothing is ever deleted; analyses are append-only
        if table == "irrigation_events" and op["kind"] == "patch":
            row = (await session.execute(text("SELECT parcel_id, author_id FROM irrigation_events WHERE farm_id = :f AND id = :i"), {"f": farm_id, "i": op["record_id"]})).first()
            if row is None or not await parcel_readable(ctx, row.parcel_id):
                raise NOT_FOUND
            if not can(role, "irrigation.correct") or (role == "worker" and row.author_id != user_id):
                raise _forbidden()
            continue
        parcel = _uuid(op["fields"].get("parcel_id"))
        if parcel is None:
            continue  # rejected as invalid at apply time (no existence oracle)
        if not await parcel_readable(ctx, parcel):
            raise NOT_FOUND
        action = {"irrigation_systems": "irrigation_system.write", "irrigation_events": "irrigation.record", "water_analyses": "water_analysis.write"}[table]
        if not can(role, action):
            raise _forbidden()
        owner_table = {"irrigation_events": "irrigation_events", "water_analyses": "water_analyses"}.get(table)
        if owner_table:  # a client id that names an object of ANOTHER farm is indistinguishable from an unknown parcel
            other = (await session.execute(text(f"SELECT farm_id FROM {owner_table} WHERE id = :i"), {"i": op["record_id"]})).first()
            if other is not None and other.farm_id != farm_id:
                raise NOT_FOUND


def _rejected(op_id: uuid.UUID, code: str, field: str | None = None) -> Result:
    return {"op_id": str(op_id), "status": "rejected", "error": {"code": code, **({"field": field} if field else {})}}


async def apply_op(session: AsyncSession, user_id: uuid.UUID, op: dict[str, Any], now: dt.datetime) -> Result:
    op_id: uuid.UUID = op["op_id"]
    seen = await session.get(AppliedOp, op_id)
    if seen is not None:
        return {**seen.result, "status": "duplicate"}
    async with session.begin_nested():
        result = await _dispatch(session, user_id, op, now)
    session.add(AppliedOp(op_id=op_id, record_id=op["record_id"], result=result))
    if result["status"] in ("applied", "duplicate"):
        await cache.bump_data_version(op["farm_id"])
    return result


def _invalid(op_id: uuid.UUID, e: ValidationError) -> Result:
    if "invalid_object_ref" in str(e):
        return _rejected(op_id, "invalid_object_ref")
    loc = e.errors()[0]["loc"]
    return _rejected(op_id, "validation", str(loc[0]) if loc else None)


async def _dispatch(session: AsyncSession, user_id: uuid.UUID, op: dict[str, Any], now: dt.datetime) -> Result:
    op_id, farm_id, record_id = op["op_id"], op["farm_id"], op["record_id"]
    await session.execute(text(_FARM_LOCK), {"farm": str(farm_id)})
    raw: dict[str, Any] = dict(op["fields"])
    role = await farm_role(session, farm_id, user_id)
    if role is None:
        return _rejected(op_id, "not_found")
    day = _date(raw.get("performed_on"))
    if op["table"] == "irrigation_events" and op["kind"] == "put" and _uuid(raw.get("parcel_id")) and day is not None:
        # cheap early refusal under the lock; service.record_event rechecks every quota in the same transaction
        taken = (await session.execute(
            text("SELECT count(*) FROM irrigation_events WHERE farm_id = :f AND parcel_id = :p AND performed_on = :d AND status = 'done'"
                 " AND sector_no IS NOT DISTINCT FROM CAST(:s AS integer)"),
            {"f": farm_id, "p": _uuid(raw["parcel_id"]), "d": day, "s": raw.get("sector_no")},
        )).scalar_one()
        existing = (await session.execute(text("SELECT 1 FROM irrigation_events WHERE farm_id = :f AND id = :i"), {"f": farm_id, "i": record_id})).first()
        if existing is None and taken >= LIMITS["events_per_day_sector"]:
            return _rejected(op_id, "quota_exceeded")
    if op["table"] == "irrigation_events" and op["kind"] == "patch":
        if set(raw) != {"status"} or raw["status"] != "cancelled":
            return _rejected(op_id, "validation", "status")  # the only change a client may make is the cancellation
        row = (await session.execute(text("SELECT parcel_id FROM irrigation_events WHERE farm_id = :f AND id = :i"), {"f": farm_id, "i": record_id})).first()
        if row is None:
            return _rejected(op_id, "not_found")
        await service.cancel_event(session, farm_id, user_id, role, row.parcel_id, record_id, now)
        return {"op_id": str(op_id), "status": "applied", "server_version": 1}
    parcel = _uuid(raw.pop("parcel_id", None))
    if parcel is None:
        return _rejected(op_id, "validation", "parcel_id")
    try:
        if op["table"] == "irrigation_events":
            event = IrrigationEventInput.model_validate({"id": str(record_id), **raw})
            _, created = await service.record_event(session, farm_id, user_id, parcel, event, now)
            return {"op_id": str(op_id), "status": "applied" if created else "duplicate", "server_version": 1}
        if op["table"] == "water_analyses":
            analysis = WaterAnalysisInput.model_validate({"id": str(record_id), **raw})
            _, created = await service.add_analysis(session, farm_id, user_id, parcel, analysis, now)
            return {"op_id": str(op_id), "status": "applied" if created else "duplicate", "server_version": 1}
        system = IrrigationSystemInput.model_validate(raw)
        current = (await session.execute(text("SELECT id FROM irrigation_systems WHERE farm_id = :f AND parcel_id = :p"), {"f": farm_id, "p": parcel})).first()
        if current is not None and current.id != record_id:
            return _rejected(op_id, "system_exists")  # one active installation per parcel
        await service.put_system(session, farm_id, user_id, parcel, system.model_copy(update={"id": record_id}), now)
        return {"op_id": str(op_id), "status": "applied", "server_version": 1}
    except ValidationError as e:
        return _invalid(op_id, e)
    except service.Refusal as e:
        return _rejected(op_id, e.code, e.field)
    except service.QuotaExceeded as e:
        return _rejected(op_id, "quota_exceeded", e.code)
    except HTTPException as e:
        return _rejected(op_id, "not_found" if e.status_code == 404 else "forbidden")
