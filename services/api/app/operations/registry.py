"""Regulatory phyto registry (G4): append-only entries, compensating reversals, frozen snapshot.

An entry is never updated: a correction inserts a `reversal` that points at the application it cancels
(`supersedes_id`), then a new `application`. The view `registry_current` shows applications without reversal.
"""
import datetime as dt
import json
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.domain.allocation import allocate

_COPY = (
    "farm_id, operation_id, parcel_id, performed_on, parcel_name, crop_name, area_ha, product_id, product_name,"
    " active_ingredients, is_free_product, dose, dose_unit, allocated_quantity, dar_days, max_dose,"
    " catalog_version_id, operator_name, operator_user_id, warnings, season_id, retain_until"
)


def _plus_years(day: dt.date, years: int) -> dt.date:
    try:
        return day.replace(year=day.year + years)
    except ValueError:  # 29 February
        return day.replace(year=day.year + years, day=28)


def retain_until(performed_on: dt.date, *, recorded_on: dt.date, years: int | None = None) -> dt.date:
    """max(performed_on, recorded_on) + the retention period (default AYLAL_REGISTRY_RETENTION_YEARS, 5 years).

    A backdated operation never shortens the legal retention: it runs from the server recording date at least.
    """
    return _plus_years(max(performed_on, recorded_on), years if years is not None else get_settings().registry_retention_years)


async def _chain_retention(session: AsyncSession, farm_id: uuid.UUID, operation_id: uuid.UUID) -> dt.date | None:
    """Longest retain_until already recorded for the operation (its applications and reversals)."""
    return (
        await session.execute(
            text("SELECT max(retain_until) FROM registry_entries WHERE farm_id = :f AND operation_id = :o"),
            {"f": farm_id, "o": operation_id},
        )
    ).scalar()


def product_lines(op: dict[str, Any]) -> list[dict[str, Any]]:
    """The product lines of an operation: explicit lines, else the single product columns, else one empty line."""
    lines = op.get("product_lines") or []
    if lines:
        return [dict(line) for line in lines]
    single = {k: op.get(k) for k in ("product_id", "free_product_name", "dose", "dose_unit")}
    return [single]


async def _operator_name(session: AsyncSession, op: dict[str, Any]) -> str:
    if op.get("operator_name"):
        return str(op["operator_name"])
    who = op.get("operator_user_id") or op["author_id"]
    name = (await session.execute(text("SELECT display_name FROM users WHERE id = :u"), {"u": who})).scalar()
    return str(name or "")


async def write_applications(
    session: AsyncSession, op: dict[str, Any], parcels: list[dict[str, Any]], user_id: uuid.UUID
) -> list[uuid.UUID]:
    """Insert one `application` per parcel and product line, with the snapshot of that moment."""
    operator = await _operator_name(session, op)
    retain = retain_until(op["performed_on"], recorded_on=dt.date.today())
    longest = await _chain_retention(session, op["farm_id"], op["id"])
    if longest is not None:
        retain = max(retain, longest)
    areas = [float(p["area_ha"] or 0) for p in parcels]
    weights = areas if sum(areas) > 0 else [1.0] * len(parcels)
    quantity = op.get("quantity_total")
    shares = allocate(Decimal(str(quantity)), weights) if quantity is not None else [None] * len(parcels)
    ids: list[uuid.UUID] = []
    for line in product_lines(op):
        product = await _product(session, line.get("product_id"))
        for parcel, share in zip(parcels, shares, strict=True):
            uses = await _use(session, line.get("product_id"), parcel.get("crop_slug"))
            entry_id = uuid.uuid4()
            ids.append(entry_id)
            await session.execute(
                text(
                    "INSERT INTO registry_entries (id, entry_kind, recorded_by, " + _COPY + ") VALUES"
                    " (:id, 'application', :by, :farm, :op, :parcel, :on, :pname, :cname, :area, :pid, :prod,"
                    " CAST(:ai AS jsonb), :free, :dose, :unit, :alloc, :dar, :maxdose, :cat, :operator, :ouser,"
                    " CAST(:warn AS jsonb), :season, :retain)"
                ),
                {
                    "id": entry_id, "by": user_id, "farm": op["farm_id"], "op": op["id"], "parcel": parcel["id"],
                    "on": op["performed_on"], "pname": parcel["name"], "cname": parcel.get("crop_name"),
                    "area": parcel["area_ha"], "pid": line.get("product_id"),
                    "prod": product["name"] if product else (line.get("free_product_name") or ""),
                    "ai": json.dumps(product["active_ingredients"] if product else []),
                    "free": product is None and bool(line.get("free_product_name")),
                    "dose": line.get("dose"), "unit": line.get("dose_unit"), "alloc": share,
                    "dar": uses.get("dar_days") if uses else None, "maxdose": uses.get("max_dose") if uses else None,
                    "cat": product["catalog_version_id"] if product else None, "operator": operator,
                    "ouser": op.get("operator_user_id"),
                    "warn": json.dumps([w for w in op.get("warnings") or [] if w.get("parcel_id") in (None, str(parcel["id"]))]),
                    "season": op.get("season_id"), "retain": retain,
                },
            )
    return ids


async def reverse_current(session: AsyncSession, farm_id: uuid.UUID, operation_id: uuid.UUID, user_id: uuid.UUID) -> int:
    """Compensate every current application of the operation with a `reversal` copy."""
    result = await session.execute(
        text(
            "INSERT INTO registry_entries (id, entry_kind, supersedes_id, recorded_by, " + _COPY + ")"
            " SELECT gen_random_uuid(), 'reversal', id, :by, " + _COPY + " FROM registry_current"
            " WHERE farm_id = :farm AND operation_id = :op ORDER BY recorded_at, id"
        ),
        {"by": user_id, "farm": farm_id, "op": operation_id},
    )
    return int(result.rowcount or 0)  # type: ignore[attr-defined]


async def _product(session: AsyncSession, product_id: Any) -> dict[str, Any] | None:
    if product_id is None:
        return None
    row = (
        await session.execute(
            text("SELECT name, active_ingredients, catalog_version_id FROM phyto_products WHERE id = :i"), {"i": product_id}
        )
    ).mappings().first()
    return dict(row) if row else None


async def _use(session: AsyncSession, product_id: Any, crop_slug: str | None) -> dict[str, Any] | None:
    if product_id is None or crop_slug is None:
        return None
    row = (
        await session.execute(
            text(
                "SELECT dar_days, max_dose FROM phyto_product_uses WHERE product_id = :p AND crop_slug = :c"
                " ORDER BY dar_days DESC NULLS LAST LIMIT 1"
            ),
            {"p": product_id, "c": crop_slug},
        )
    ).mappings().first()
    return dict(row) if row else None


def entry_json(row: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, Decimal):
            out[key] = float(value)
        elif isinstance(value, uuid.UUID):
            out[key] = str(value)
        elif isinstance(value, (dt.date, dt.datetime)):
            out[key] = value.isoformat()
        else:
            out[key] = value
    return out


async def list_entries(
    session: AsyncSession, farm_id: uuid.UUID, *, parcel_id: uuid.UUID | None, start: dt.date | None,
    end: dt.date | None, limit: int, after: tuple[dt.date, uuid.UUID] | None,
) -> tuple[list[dict[str, Any]], bool]:
    """Current view of the registry, newest first; returns (items, has_more)."""
    clauses = ["farm_id = :farm"]
    params: dict[str, Any] = {"farm": farm_id, "n": limit + 1}
    if parcel_id is not None:
        clauses.append("parcel_id = :parcel")
        params["parcel"] = parcel_id
    if start is not None:
        clauses.append("performed_on >= :start")
        params["start"] = start
    if end is not None:
        clauses.append("performed_on <= :end")
        params["end"] = end
    if after is not None:
        clauses.append("(performed_on, id) < (:aon, :aid)")
        params["aon"], params["aid"] = after
    rows = (
        await session.execute(
            text(f"SELECT * FROM registry_current WHERE {' AND '.join(clauses)} ORDER BY performed_on DESC, id DESC LIMIT :n"),
            params,
        )
    ).mappings().all()
    return [entry_json(dict(r)) for r in rows[:limit]], len(rows) > limit
