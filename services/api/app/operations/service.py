"""Operations journal service (G1, G3, G4).

Every write that is bounded by a quota first takes the per-farm advisory lock (same transaction as the write,
REST and sync alike), then reads the figures it needs, then writes: two concurrent requests can never both
take the last slot.
"""
import datetime as dt
import json
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.allocation import allocate
from app.domain.operation_limits import LIMITS, valid_dose, within_limit
from app.domain.operation_rules import initial_status, is_overdue, next_status
from app.domain.phyto_controls import phyto_warnings
from app.operations import access, label, registry

_LOCK = "SELECT pg_advisory_xact_lock(hashtextextended(CAST(:farm AS text), 0))"
_DONE_STATES = ("done", "pending_validation", "validated")


class OperationError(Exception):
    def __init__(self, status: int, code: str, field: str | None = None) -> None:
        super().__init__(code)
        self.status, self.code, self.field = status, code, field


async def lock_farm(session: AsyncSession, farm_id: uuid.UUID) -> None:
    """Serialise quota-bounded writes of one farm until the end of the transaction."""
    await session.execute(text(_LOCK), {"farm": str(farm_id)})


async def check_quotas(session: AsyncSession, farm_id: uuid.UUID, performed_on: dt.date, status: str) -> None:
    """Yearly cap and planned cap of a farm; call after lock_farm."""
    year = (
        await session.execute(
            text(
                "SELECT count(*) FROM operations WHERE farm_id = :f"
                " AND performed_on >= make_date(:y, 1, 1) AND performed_on < make_date(:y1, 1, 1)"
            ),
            {"f": farm_id, "y": performed_on.year, "y1": performed_on.year + 1},
        )
    ).scalar_one()
    if year >= LIMITS["ops_per_farm_year"]:
        raise OperationError(413, "operations_quota_exceeded")
    if status == "planned":
        planned = (
            await session.execute(
                text("SELECT count(*) FROM operations WHERE farm_id = :f AND status = 'planned'"), {"f": farm_id}
            )
        ).scalar_one()
        if planned >= LIMITS["planned_count"]:
            raise OperationError(413, "planned_quota_exceeded")


def _num(value: Any) -> Any:
    return float(value) if isinstance(value, Decimal) else value


def _clean(row: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, (dt.date, dt.datetime)):
            out[key] = value.isoformat()
        elif isinstance(value, uuid.UUID):
            out[key] = str(value)
        else:
            out[key] = _num(value)
    return out


def _typed(data: dict[str, Any]) -> dict[str, Any]:
    """Body fields with database types (dates, UUIDs, decimals)."""
    out = dict(data)
    if isinstance(out.get("performed_on"), str):
        out["performed_on"] = dt.date.fromisoformat(out["performed_on"])
    for key in ("id", "product_id", "season_id", "label_photo_id"):
        if out.get(key) is not None:
            out[key] = uuid.UUID(str(out[key]))
    for key in ("dose", "quantity_total"):
        if out.get(key) is not None:
            out[key] = Decimal(str(out[key]))
    if "parcel_ids" in out:
        out["parcel_ids"] = list(dict.fromkeys(uuid.UUID(str(p)) for p in out["parcel_ids"]))
    if out.get("product_lines") is not None:
        out["product_lines"] = [
            {
                "product_id": str(line["product_id"]) if line.get("product_id") else None,
                "free_product_name": line.get("free_product_name"),
                "dose": line.get("dose"),
                "dose_unit": getattr(line.get("dose_unit"), "value", line.get("dose_unit")),
            }
            for line in out["product_lines"]
        ]
    if hasattr(out.get("dose_unit"), "value"):
        out["dose_unit"] = out["dose_unit"].value
    if hasattr(out.get("type"), "value"):
        out["type"] = out["type"].value
    return out


def validate_limits(data: dict[str, Any], today: dt.date) -> None:
    """Domain caps the generated schema cannot express (dose decimals, performed_on window, exclusive product)."""
    if data.get("performed_on") is not None and not within_limit("performed_on", data["performed_on"].isoformat(), today):
        raise OperationError(422, "validation", "performed_on")
    for dose in [data.get("dose"), *[line.get("dose") for line in data.get("product_lines") or []]]:
        if dose is not None and not valid_dose(dose):
            raise OperationError(422, "validation", "dose")
    if data.get("product_id") is not None and data.get("free_product_name") is not None:
        raise OperationError(422, "validation", "free_product_name")
    for line in data.get("product_lines") or []:
        if line.get("product_id") and line.get("free_product_name"):
            raise OperationError(422, "validation", "product_lines")


async def _uses_of(session: AsyncSession, product_id: Any) -> list[dict[str, Any]]:
    rows = (
        await session.execute(
            text("SELECT crop_slug, max_dose, dose_unit, dar_days, max_applications FROM phyto_product_uses WHERE product_id = :p"),
            {"p": uuid.UUID(str(product_id))},
        )
    ).mappings().all()
    return [{**dict(r), "max_dose": _num(r["max_dose"])} for r in rows]


async def _applications_so_far(
    session: AsyncSession, farm_id: uuid.UUID, parcel_id: uuid.UUID, product_id: Any, season_id: Any, exclude: Any,
) -> int:
    """Live (not reversed) applications of this product on the parcel in the campaign, other operations only."""
    return int(
        (
            await session.execute(
                text(
                    "SELECT count(*) FROM registry_current WHERE farm_id = :f AND parcel_id = :p AND product_id = :prod"
                    " AND season_id IS NOT DISTINCT FROM :s AND (CAST(:x AS uuid) IS NULL OR operation_id <> :x)"
                ),
                {"f": farm_id, "p": parcel_id, "prod": uuid.UUID(str(product_id)), "s": season_id, "x": exclude},
            )
        ).scalar_one()
    )


async def warnings_for(
    session: AsyncSession, farm_id: uuid.UUID, data: dict[str, Any], parcels: list[dict[str, Any]],
    *, exclude_operation: uuid.UUID | None = None,
) -> list[dict[str, Any]]:
    """Warnings are always recomputed here (never the client's), parcel by parcel and product line by product line."""
    lines = data.get("product_lines") or [data]
    out: list[dict[str, Any]] = []
    for parcel in parcels:
        codes: list[str] = []
        for line in lines:
            product_id = line.get("product_id")
            uses = await _uses_of(session, product_id) if product_id else []
            so_far = (
                await _applications_so_far(session, farm_id, parcel["id"], product_id, data.get("season_id"), exclude_operation)
                if product_id else 0
            )
            for code in phyto_warnings({
                "product_id": str(product_id) if product_id else None, "free_product_name": line.get("free_product_name"),
                "uses": uses, "crop_slug": parcel.get("crop_slug"), "dose": line.get("dose"),
                "dose_unit": line.get("dose_unit"), "applications_so_far": so_far,
            }):
                if code not in codes:
                    codes.append(code)
        out.extend({"code": c, "parcel_id": str(parcel["id"])} for c in codes)
    return out


async def _refresh_warnings(session: AsyncSession, op: dict[str, Any], parcels: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Recompute the warnings of an existing operation (other operations only) and store them on its lines."""
    lines = _typed({"product_lines": op.get("product_lines") or []}).get("product_lines") or []
    data = {**op, "product_lines": lines}
    warnings = await warnings_for(session, op["farm_id"], data, parcels, exclude_operation=op["id"])
    for parcel in parcels:
        mine = [w for w in warnings if w["parcel_id"] == str(parcel["id"])]
        await session.execute(
            text("UPDATE operation_parcels SET warnings = CAST(:w AS jsonb) WHERE farm_id = :f AND operation_id = :o AND parcel_id = :p"),
            {"w": json.dumps(mine), "f": op["farm_id"], "o": op["id"], "p": parcel["id"]},
        )
    return warnings


async def _check_product(session: AsyncSession, data: dict[str, Any]) -> None:
    ids = {data.get("product_id"), *[line.get("product_id") for line in data.get("product_lines") or []]} - {None}
    for product_id in ids:
        found = (await session.execute(text("SELECT 1 FROM phyto_products WHERE id = :i"), {"i": uuid.UUID(str(product_id))})).first()
        if found is None:
            raise OperationError(422, "validation", "product_id")


async def _resolve_label(session: AsyncSession, farm_id: uuid.UUID, user_id: uuid.UUID, label_id: Any) -> str:
    try:
        return await label.consume(session, farm_id, user_id, label_id)
    except label.InvalidObjectRef as e:
        raise OperationError(422, "invalid_object_ref") from e


async def create_operation(
    session: AsyncSession, farm_id: uuid.UUID, user_id: uuid.UUID, role: str, body: dict[str, Any],
    *, today: dt.date | None = None,
) -> tuple[dict[str, Any], bool]:
    """Create an operation (idempotent on the client id); returns (detail, created)."""
    today = today or dt.date.today()
    data = _typed(body)
    validate_limits(data, today)
    existing = await access.load_operation(session, farm_id, data["id"])
    if existing is not None:
        return await detail(session, farm_id, data["id"], user_id, role), False
    if (await session.execute(text("SELECT 1 FROM operations WHERE id = :i"), {"i": data["id"]})).first():
        raise OperationError(404, "not_found")  # the id belongs to another farm: indistinguishable from unknown
    parcels = await access.usable_parcels(session, farm_id, user_id, role, data["parcel_ids"])
    if len(parcels) != len(data["parcel_ids"]):
        raise OperationError(404, "not_found")
    await _check_product(session, data)
    key = await _resolve_label(session, farm_id, user_id, data["label_photo_id"]) if data.get("label_photo_id") else None
    status = initial_status(data["performed_on"], today, role)
    await lock_farm(session, farm_id)
    await check_quotas(session, farm_id, data["performed_on"], status)
    warnings = await warnings_for(session, farm_id, data, parcels)
    await session.execute(
        text(
            "INSERT INTO operations (id, farm_id, type, performed_on, status, author_id, operator_user_id, operator_name,"
            " note, season_id, quantity_total, quantity_unit, label_photo_key, product_id, free_product_name, dose,"
            " dose_unit, product_lines, done_at) VALUES (:id, :farm, :type, :on, :status, :author, :ouser, :oname, :note,"
            " :season, :qty, :qunit, :key, :product, :free, :dose, :unit, CAST(:lines AS jsonb), :done)"
        ),
        {
            "id": data["id"], "farm": farm_id, "type": data["type"], "on": data["performed_on"], "status": status,
            "author": user_id, "ouser": None if data.get("operator_name") else user_id, "oname": data.get("operator_name"),
            "note": data.get("note"), "season": data.get("season_id"), "qty": data.get("quantity_total"),
            "qunit": data.get("quantity_unit"), "key": key, "product": data.get("product_id"),
            "free": data.get("free_product_name"), "dose": data.get("dose"), "unit": data.get("dose_unit"),
            "lines": json.dumps(data.get("product_lines") or []),
            "done": dt.datetime.now(dt.UTC) if status != "planned" else None,
        },
    )
    op = await access.load_operation(session, farm_id, data["id"])
    assert op is not None
    await _write_lines(session, op, parcels, warnings)
    if status == "planned":
        await session.execute(
            text("INSERT INTO operation_reminders (id, farm_id, operation_id, fire_on, state) VALUES (:i, :f, :o, :d, 'scheduled')"),
            {"i": uuid.uuid4(), "f": farm_id, "o": data["id"], "d": data["performed_on"]},
        )
    elif op["type"] == "phyto":
        await registry.write_applications(session, {**op, "warnings": warnings}, parcels, user_id)
    return await detail(session, farm_id, data["id"], user_id, role), True


async def _write_lines(session: AsyncSession, op: dict[str, Any], parcels: list[dict[str, Any]], warnings: list[dict[str, Any]]) -> None:
    """(Re)build the denormalised read model of an operation: one line per parcel."""
    await session.execute(text("DELETE FROM operation_parcels WHERE farm_id = :f AND operation_id = :o"), {"f": op["farm_id"], "o": op["id"]})
    areas = [float(p["area_ha"] or 0) for p in parcels]
    weights = areas if sum(areas) > 0 else [1.0] * len(parcels)
    quantity = op["quantity_total"]
    shares = allocate(quantity, weights) if quantity is not None else [None] * len(parcels)
    first = (op.get("product_lines") or [{}])[0] if op.get("product_lines") else {}
    for parcel, share in zip(parcels, shares, strict=True):
        await session.execute(
            text(
                "INSERT INTO operation_parcels (id, farm_id, operation_id, parcel_id, author_id, type, performed_on, status,"
                " product_id, free_product_name, allocated_quantity, allocated_dose, dose_unit, area_ha_snapshot, crop_slug,"
                " warnings) VALUES (:id, :f, :o, :p, :a, :t, :on, :s, :prod, :free, :alloc, :dose, :unit, :area, :crop,"
                " CAST(:w AS jsonb))"
            ),
            {
                "id": uuid.uuid4(), "f": op["farm_id"], "o": op["id"], "p": parcel["id"], "a": op["author_id"],
                "t": op["type"], "on": op["performed_on"], "s": op["status"],
                "prod": op["product_id"] or first.get("product_id"), "free": op["free_product_name"] or first.get("free_product_name"),
                "alloc": share, "dose": op["dose"] if op["dose"] is not None else first.get("dose"),
                "unit": op["dose_unit"] or first.get("dose_unit"), "area": parcel["area_ha"], "crop": parcel.get("crop_slug"),
                "w": json.dumps([w for w in warnings if w.get("parcel_id") == str(parcel["id"])]),
            },
        )


async def detail(session: AsyncSession, farm_id: uuid.UUID, operation_id: uuid.UUID, user_id: uuid.UUID, role: str) -> dict[str, Any]:
    op = await access.load_operation(session, farm_id, operation_id)
    if op is None:
        raise OperationError(404, "not_found")
    lines = await access.lines_of(session, farm_id, operation_id, user_id, role)
    if role not in access.STAFF and not lines:
        raise OperationError(404, "not_found")
    return render(op, lines)


def render(op: dict[str, Any], lines: list[dict[str, Any]], today: dt.date | None = None) -> dict[str, Any]:
    """JSON of an operation: the storage key is never part of it."""
    out = _clean({k: v for k, v in op.items() if k not in ("label_photo_key", "field_versions")})
    out["has_label_photo"] = op.get("label_photo_key") is not None
    out["overdue"] = is_overdue(op["status"], op["performed_on"], today or dt.date.today())
    out["parcels"] = [
        _clean({k: v for k, v in line.items() if k in (
            "parcel_id", "allocated_quantity", "allocated_dose", "dose_unit", "area_ha_snapshot", "crop_slug", "warnings",
            "parcel_archived_at")})
        for line in lines
    ]
    out["warnings"] = [w for line in lines for w in line["warnings"]]
    return out


async def list_page(
    session: AsyncSession, farm_id: uuid.UUID, user_id: uuid.UUID, role: str, *, limit: int,
    after: tuple[dt.date, uuid.UUID] | None, parcel_id: uuid.UUID | None, type_: str | None, status: str | None,
) -> tuple[list[dict[str, Any]], bool]:
    clauses = ["o.farm_id = :f"]
    params: dict[str, Any] = {"f": farm_id, "uid": user_id, "n": limit + 1}
    line = access.visible_lines(role)
    sub = f"EXISTS (SELECT 1 FROM operation_parcels l WHERE l.farm_id = o.farm_id AND l.operation_id = o.id AND {line}"
    if parcel_id is not None:
        sub += " AND l.parcel_id = :parcel"
        params["parcel"] = parcel_id
    clauses.append(sub + ")")
    if type_:
        clauses.append("o.type = :type")
        params["type"] = type_
    if status:
        clauses.append("o.status = :status")
        params["status"] = status
    if after is not None:
        clauses.append("(o.performed_on, o.id) < (:aon, :aid)")
        params["aon"], params["aid"] = after
    rows = (
        await session.execute(
            text(f"SELECT o.* FROM operations o WHERE {' AND '.join(clauses)} ORDER BY o.performed_on DESC, o.id DESC LIMIT :n"),
            params,
        )
    ).mappings().all()
    items = []
    for row in rows[:limit]:
        lines = await access.lines_of(session, farm_id, row["id"], user_id, role)
        items.append(render(dict(row), lines))
    return items, len(rows) > limit


async def _sync_lines(session: AsyncSession, op: dict[str, Any]) -> None:
    await session.execute(
        text(
            "UPDATE operation_parcels SET status = :s, performed_on = :on, product_id = :p, free_product_name = :n,"
            " dose_unit = COALESCE(:u, dose_unit), allocated_dose = COALESCE(:d, allocated_dose), updated_at = now()"
            " WHERE farm_id = :f AND operation_id = :o"
        ),
        {"s": op["status"], "on": op["performed_on"], "p": op["product_id"], "n": op["free_product_name"],
         "u": op["dose_unit"], "d": op["dose"], "f": op["farm_id"], "o": op["id"]},
    )


async def _parcels_of(session: AsyncSession, op: dict[str, Any]) -> list[dict[str, Any]]:
    """Parcels of the operation with their snapshot data (archived ones included: history stays readable)."""
    rows = (
        await session.execute(
            text(
                "SELECT l.parcel_id AS id, p.name, l.area_ha_snapshot AS area_ha, l.crop_slug,"
                " (SELECT c.name_fr FROM crops c WHERE c.slug = l.crop_slug AND c.farm_id IS NULL LIMIT 1) AS crop_name"
                " FROM operation_parcels l JOIN parcels p ON p.id = l.parcel_id AND p.farm_id = l.farm_id"
                " WHERE l.farm_id = :f AND l.operation_id = :o ORDER BY l.parcel_id"
            ),
            {"f": op["farm_id"], "o": op["id"]},
        )
    ).mappings().all()
    return [dict(r) for r in rows]


async def _actor_operation(
    session: AsyncSession, farm_id: uuid.UUID, operation_id: uuid.UUID, user_id: uuid.UUID, role: str
) -> dict[str, Any]:
    """The operation for an acting user: staff any, a worker only their own and only when every line is visible."""
    op = await access.load_operation(session, farm_id, operation_id)
    if op is None:
        raise OperationError(404, "not_found")
    if role not in access.STAFF:
        if op["author_id"] != user_id:
            raise OperationError(403, "forbidden")
        if not await access.can_see(session, farm_id, operation_id, user_id, role):
            raise OperationError(404, "not_found")
    return op


async def reschedule(
    session: AsyncSession, farm_id: uuid.UUID, operation_id: uuid.UUID, user_id: uuid.UUID, role: str,
    new_date: dt.date, *, today: dt.date | None = None,
) -> dict[str, Any]:
    """Move a planned operation to a date that is not in the past; its reminder follows the new date."""
    today = today or dt.date.today()
    op = await _actor_operation(session, farm_id, operation_id, user_id, role)
    if next_status(op["status"], "reschedule", role) is None:
        raise OperationError(409, "invalid_transition")
    if new_date < today or not within_limit("performed_on", new_date.isoformat(), today):
        raise OperationError(422, "validation", "performed_on")
    await session.execute(
        text("UPDATE operations SET performed_on = :d, updated_at = now(), server_version = server_version + 1 WHERE id = :i AND farm_id = :f"),
        {"d": new_date, "i": operation_id, "f": farm_id},
    )
    await session.execute(
        text("UPDATE operation_parcels SET performed_on = :d, updated_at = now() WHERE farm_id = :f AND operation_id = :i"),
        {"d": new_date, "i": operation_id, "f": farm_id},
    )
    await session.execute(text("DELETE FROM operation_reminders WHERE farm_id = :f AND operation_id = :i AND state <> 'done'"), {"f": farm_id, "i": operation_id})
    await session.execute(
        text("INSERT INTO operation_reminders (id, farm_id, operation_id, fire_on, state) VALUES (:r, :f, :i, :d, 'scheduled')"),
        {"r": uuid.uuid4(), "f": farm_id, "i": operation_id, "d": new_date},
    )
    return await detail(session, farm_id, operation_id, user_id, role)


async def transition(
    session: AsyncSession, farm_id: uuid.UUID, operation_id: uuid.UUID, user_id: uuid.UUID, role: str, action: str
) -> dict[str, Any]:
    """mark_done, validate or cancel; the registry follows (application at completion, reversal at cancellation)."""
    op = await _actor_operation(session, farm_id, operation_id, user_id, role)
    new = next_status(op["status"], action, role)
    if new is None:
        denied = role not in access.STAFF and (action in ("validate", "correct") or op["status"] != "planned")
        raise OperationError(403 if denied else 409, "forbidden" if denied else "invalid_transition")
    previous = op["status"]
    await session.execute(
        text(
            "UPDATE operations SET status = :s, updated_at = now(), server_version = server_version + 1,"
            " done_at = CASE WHEN :a = 'mark_done' THEN now() ELSE done_at END,"
            " validated_by = CASE WHEN :s = 'validated' THEN :u ELSE validated_by END,"
            " validated_at = CASE WHEN :s = 'validated' THEN now() ELSE validated_at END WHERE id = :i AND farm_id = :f"
        ),
        {"s": new, "a": action, "u": user_id, "i": operation_id, "f": farm_id},
    )
    op = {**op, "status": new}
    await _sync_lines(session, op)
    if action == "mark_done":
        await session.execute(text("UPDATE operation_reminders SET state = 'done' WHERE farm_id = :f AND operation_id = :o"), {"f": farm_id, "o": operation_id})
        if op["type"] == "phyto":
            parcels = await _parcels_of(session, op)
            warnings = await _refresh_warnings(session, op, parcels)
            await registry.write_applications(session, {**op, "warnings": warnings}, parcels, user_id)
    elif action == "cancel":
        await session.execute(text("UPDATE operation_reminders SET state = 'dismissed' WHERE farm_id = :f AND operation_id = :o AND state = 'scheduled'"), {"f": farm_id, "o": operation_id})
        if previous in _DONE_STATES and op["type"] == "phyto":
            await registry.reverse_current(session, farm_id, operation_id, user_id)
    return await detail(session, farm_id, operation_id, user_id, role)


_CORRECTABLE = (
    "performed_on", "product_id", "free_product_name", "dose", "dose_unit", "quantity_total", "quantity_unit",
    "operator_name", "note",
)


async def correct(
    session: AsyncSession, farm_id: uuid.UUID, operation_id: uuid.UUID, user_id: uuid.UUID, role: str,
    changes: dict[str, Any], *, source: str = "manual", today: dt.date | None = None, base_version: int | None = None,
) -> dict[str, Any]:
    """Correct an operation (staff). Each change is logged; a done phyto treatment gets a reversal then a new application."""
    op = await access.load_operation(session, farm_id, operation_id)
    if op is None:
        raise OperationError(404, "not_found")
    if op["status"] != "planned" and next_status(op["status"], "correct", role) is None:
        raise OperationError(403 if role not in access.STAFF else 409, "forbidden" if role not in access.STAFF else "invalid_transition")
    data = _typed(changes)
    validate_limits(data, today or dt.date.today())
    merged = {**op, **{k: v for k, v in data.items() if k in _CORRECTABLE or k == "product_lines"}}
    if merged.get("product_id") is not None and merged.get("free_product_name") is not None:
        if "product_id" in data and "free_product_name" not in data:
            merged["free_product_name"] = None
        elif "free_product_name" in data and "product_id" not in data:
            merged["product_id"] = None
    await _check_product(session, merged)
    diff = {k: merged[k] for k in (*_CORRECTABLE, "product_lines") if k in data and merged.get(k) != op.get(k)}
    for k in ("product_id", "free_product_name"):
        if merged.get(k) != op.get(k):
            diff[k] = merged.get(k)
    key = None
    if data.get("label_photo_id") is not None:
        key = await _resolve_label(session, farm_id, user_id, data["label_photo_id"])
    if not diff and key is None:
        return await detail(session, farm_id, operation_id, user_id, role)
    registry_phyto = op["type"] == "phyto" and op["status"] in _DONE_STATES and bool(diff)
    new_ids: list[uuid.UUID] = []
    updated = {**op, **diff}
    if registry_phyto:
        await registry.reverse_current(session, farm_id, operation_id, user_id)
    sets = ", ".join(f"{k} = :{k}" for k in diff if k != "product_lines")
    params: dict[str, Any] = {k: v for k, v in diff.items() if k != "product_lines"}
    if "product_lines" in diff:
        sets = (sets + ", " if sets else "") + "product_lines = CAST(:product_lines AS jsonb)"
        params["product_lines"] = json.dumps(diff["product_lines"])
    if key is not None:
        sets = (sets + ", " if sets else "") + "label_photo_key = :label_key"
        params["label_key"] = key
    await session.execute(
        text(f"UPDATE operations SET {sets}, updated_at = now(), server_version = server_version + 1 WHERE id = :_id AND farm_id = :_farm"),
        {**params, "_id": operation_id, "_farm": farm_id},
    )
    await _sync_lines(session, updated)
    parcels = await _parcels_of(session, updated)
    warnings = await _refresh_warnings(session, updated, parcels)
    if registry_phyto:
        new_ids = await registry.write_applications(session, {**updated, "warnings": warnings}, parcels, user_id)
    new_version = int(op["server_version"]) + 1
    for field, value in diff.items():
        stale = base_version is not None and base_version < int(op["server_version"]) and (
            await session.execute(
                text("SELECT 1 FROM operation_corrections WHERE farm_id = :f AND operation_id = :o AND field = :field AND server_version > :bv LIMIT 1"),
                {"f": farm_id, "o": operation_id, "field": field, "bv": base_version},
            )
        ).first() is not None
        await session.execute(
            text(
                "INSERT INTO operation_corrections (id, farm_id, operation_id, field, before, after, author_id, source,"
                " registry_entry_id, server_version) VALUES (:i, :f, :o, :field, CAST(:b AS jsonb), CAST(:a AS jsonb), :u,"
                " :src, :r, :sv)"
            ),
            {"i": uuid.uuid4(), "f": farm_id, "o": operation_id, "field": field, "b": json.dumps(op.get(field), default=str),
             "a": json.dumps(value, default=str), "u": user_id, "src": "sync_conflict" if stale else source,
             "r": new_ids[0] if new_ids else None, "sv": new_version},
        )
    return await detail(session, farm_id, operation_id, user_id, role)


async def corrections(session: AsyncSession, farm_id: uuid.UUID, operation_id: uuid.UUID) -> list[dict[str, Any]]:
    if await access.load_operation(session, farm_id, operation_id) is None:
        raise OperationError(404, "not_found")
    rows = (
        await session.execute(
            text(
                "SELECT id, field, before, after, author_id, corrected_at, source FROM operation_corrections"
                " WHERE farm_id = :f AND operation_id = :o ORDER BY corrected_at, id"
            ),
            {"f": farm_id, "o": operation_id},
        )
    ).mappings().all()
    return [_clean(dict(r)) for r in rows]


async def check(
    session: AsyncSession, farm_id: uuid.UUID, user_id: uuid.UUID, role: str, body: dict[str, Any], *, today: dt.date | None = None
) -> dict[str, Any]:
    """Controls without recording: validation, parcel visibility and warnings."""
    data = _typed(body)
    validate_limits(data, today or dt.date.today())
    parcels = await access.usable_parcels(session, farm_id, user_id, role, data["parcel_ids"])
    if len(parcels) != len(data["parcel_ids"]):
        raise OperationError(404, "not_found")
    await _check_product(session, data)
    return {"warnings": await warnings_for(session, farm_id, data, parcels)}
