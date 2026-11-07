"""Idempotent application of one client operation (FR-013, FR-015, FR-018)."""
import datetime as dt
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.access import WRITE_ROLES, farm_role
from app.db.models import AppliedOp, SyncConflict, TrialRecord
from app.domain.conflict import resolve_field_conflicts
from app.domain.validation import validate

FIELDS = ("title", "note", "quantity")
Result = dict[str, Any]


def _rejected(op_id: uuid.UUID, code: str, field: str | None = None) -> Result:
    error: dict[str, str] = {"code": code}
    if field:
        error["field"] = field
    return {"op_id": str(op_id), "status": "rejected", "error": error}


def _current_fields(row: TrialRecord) -> dict[str, Any]:
    quantity = None if row.quantity is None else float(row.quantity)
    return {"title": row.title, "note": row.note, "quantity": quantity}


def _clean(changes: dict[str, Any]) -> dict[str, Any]:
    cleaned = {k: v for k, v in changes.items() if k in FIELDS}
    if isinstance(cleaned.get("title"), str):
        cleaned["title"] = cleaned["title"].strip()
    return cleaned


async def apply_op(session: AsyncSession, user_id: uuid.UUID, op: dict[str, Any]) -> Result:
    """Apply one op inside the caller's transaction; a replayed op_id returns the recorded result."""
    op_id: uuid.UUID = op["op_id"]
    record_id: uuid.UUID = op["record_id"]
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": str(record_id)}
    )
    seen = await session.get(AppliedOp, op_id)
    if seen is not None:
        return {**seen.result, "status": "duplicate"}

    row = (
        await session.execute(
            select(TrialRecord).where(TrialRecord.id == record_id).with_for_update()
        )
    ).scalar_one_or_none()
    farm_id: uuid.UUID | None = row.farm_id if row else op.get("farm_id")
    if farm_id is None:
        return _rejected(op_id, "validation", "farm_id")
    role = await farm_role(session, farm_id, user_id)
    if role not in WRITE_ROLES:
        return _rejected(op_id, "forbidden")

    if op["kind"] == "delete":
        if row is None:
            return _rejected(op_id, "not_found")
        row.deleted_at = func.now()
        row.updated_at = func.now()
        row.server_version += 1
        result: Result = {
            "op_id": str(op_id), "status": "applied", "server_version": row.server_version
        }
    else:
        outcome = _apply_fields(op, row)
        if outcome.get("status") == "rejected":
            return outcome
        result = await _write(session, user_id, op, row, farm_id, outcome)

    session.add(AppliedOp(op_id=op_id, record_id=record_id, result=result))
    return result


def _apply_fields(op: dict[str, Any], row: TrialRecord | None) -> Result | dict[str, Any]:
    """Validate the merged record; returns a rejection or the resolution."""
    op_id: uuid.UUID = op["op_id"]
    if row is None and op["kind"] == "patch":
        return _rejected(op_id, "not_found")
    changes = _clean(op["fields"])
    base = _current_fields(row) if row else {}
    verdict = validate("trial_record.create", {**base, **changes})
    if not verdict["valid"]:
        return _rejected(op_id, "validation", verdict["errors"][0]["field"])
    record = {
        "fields": base,
        "field_versions": dict(row.field_versions) if row else {},
        "server_version": row.server_version if row else 0,
    }
    return resolve_field_conflicts(
        record,
        {
            "op_id": str(op_id),
            "author_id": str(op["author_id"]),
            "base_version": op["base_version"],
            "changes": changes,
        },
    )


async def _write(
    session: AsyncSession,
    user_id: uuid.UUID,
    op: dict[str, Any],
    row: TrialRecord | None,
    farm_id: uuid.UUID,
    res: dict[str, Any],
) -> Result:
    fields = res["fields"]
    quantity = fields.get("quantity")
    values = {
        "title": fields["title"],
        "note": fields.get("note"),
        "quantity": None if quantity is None else Decimal(str(quantity)),
        "server_version": res["server_version"],
        "field_versions": res["field_versions"],
    }
    if row is None:
        row = TrialRecord(id=op["record_id"], farm_id=farm_id, author_id=user_id, has_conflict=False)
        session.add(row)
    for key, value in values.items():
        setattr(row, key, value)
    row.updated_at = func.now()
    if res["has_conflict"]:
        row.has_conflict = True
    for c in res["conflicts"]:
        session.add(
            SyncConflict(
                id=uuid.uuid4(),
                farm_id=farm_id,
                record_id=op["record_id"],
                field=c["field"],
                discarded_value=c["discarded_value"],
                kept_value=c["kept_value"],
                discarded_by=user_id,
                base_version=c["base_version"],
                server_version=c["server_version"],
                detected_at=dt.datetime.now(dt.UTC),
            )
        )
    status = "conflict_logged" if res["has_conflict"] else "applied"
    return {"op_id": str(op["op_id"]), "status": status, "server_version": res["server_version"]}
