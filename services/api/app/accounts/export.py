"""Complete personal-data export (FR-026): only what belongs to the user, never hashes or others' data."""
import uuid
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Consent, Farm, FarmMember, TrialRecord, User
from app.operations.access import visible_lines

_FIELD_SCOPE = (
    "p.farm_id = ANY(:farms) AND (p.farm_id = ANY(:wide) OR (p.archived_at IS NULL AND EXISTS ("
    "SELECT 1 FROM worker_parcels w WHERE w.parcel_id = p.id AND w.farm_id = p.farm_id AND w.user_id = :u)))"
)


async def _field_data(session: AsyncSession, user_id: uuid.UUID, roles: list[tuple[uuid.UUID, str]]) -> dict[str, Any]:
    """Fields, seasons, blocks and free crops of the user's farms; a worker only gets the fields assigned to them."""
    params = {
        "u": user_id,
        "farms": [f for f, _ in roles],
        "wide": [f for f, r in roles if r != "worker"],
    }

    async def rows(sql: str) -> list[dict[str, Any]]:
        return [r[0] for r in (await session.execute(text(f"SELECT to_jsonb(t) FROM ({sql}) t"), params)).all()]

    fields = await rows(
        "SELECT p.id, p.farm_id, p.name, ST_AsGeoJSON(p.geometry)::json AS geometry, p.area_calc_ha::float8 AS area_calc_ha,"
        " p.area_declared_ha::float8 AS area_declared_ha, p.irrigation, p.greenhouse, p.soil, p.archived_at"
        f" FROM parcels p WHERE {_FIELD_SCOPE} ORDER BY p.name, p.id"
    )
    seasons = await rows(
        "SELECT s.id, s.farm_id, s.field_id, s.crop_id, s.variety, s.planting_year, s.sowing_date, s.started_at, s.ended_at,"
        " s.stage_estimated, s.stage_corrected, s.destination FROM seasons s JOIN parcels p ON p.id = s.field_id"
        f" AND p.farm_id = s.farm_id WHERE {_FIELD_SCOPE} ORDER BY s.started_at, s.id"
    )
    blocks = await rows(
        "SELECT b.id, b.farm_id, b.field_id, b.name, b.kind, ST_AsGeoJSON(b.geometry)::json AS geometry,"
        " b.area_calc_ha::float8 AS area_calc_ha FROM field_blocks b JOIN parcels p ON p.id = b.field_id"
        f" AND p.farm_id = b.farm_id WHERE {_FIELD_SCOPE} ORDER BY b.id"
    )
    crops = await rows(
        "SELECT c.id, c.farm_id, c.slug, c.name_ary, c.name_ar, c.name_fr, c.cycle FROM crops c"
        " WHERE c.farm_id = ANY(:wide) ORDER BY c.slug, c.id"
    )
    return {"fields": fields, "seasons": seasons, "blocks": blocks, "crops": crops}


async def _f6_data(session: AsyncSession, user_id: uuid.UUID, roles: list[tuple[uuid.UUID, str]]) -> dict[str, Any]:
    """F6: operations the user authored (a worker only on parcels still visible to them) and, for staff, the registry."""
    params = {"uid": user_id, "farms": [f for f, _ in roles], "wide": [f for f, r in roles if r != "worker"]}

    async def rows(sql: str) -> list[dict[str, Any]]:
        return [r[0] for r in (await session.execute(text(f"SELECT to_jsonb(t) FROM ({sql}) t"), params)).all()]

    operations = await rows(
        "SELECT o.id, o.farm_id, o.type, o.performed_on, o.status, o.operator_name, o.note, o.created_at FROM operations o"
        " WHERE o.farm_id = ANY(:farms) AND o.author_id = :uid AND (o.farm_id = ANY(:wide) OR EXISTS (SELECT 1 FROM operation_parcels l"
        f" WHERE l.farm_id = o.farm_id AND l.operation_id = o.id AND {visible_lines('worker')})) ORDER BY o.performed_on, o.id"
    )
    registry = await rows(
        "SELECT r.id, r.farm_id, r.operation_id, r.parcel_id, r.entry_kind, r.performed_on, r.parcel_name, r.crop_name, r.area_ha,"
        " r.product_name, r.is_free_product, r.dose, r.dose_unit, r.allocated_quantity, r.operator_name, r.recorded_at, r.retain_until"
        " FROM registry_entries r WHERE r.farm_id = ANY(:wide) ORDER BY r.performed_on, r.recorded_at, r.id"
    )
    return {"operations": operations, "registry": registry}


async def build_export(session: AsyncSession, user_id: uuid.UUID) -> dict[str, Any]:
    user = (await session.execute(select(User).where(User.id == user_id))).scalar_one()
    consents = (
        await session.execute(select(Consent).where(Consent.user_id == user_id).order_by(Consent.granted_at))
    ).scalars().all()
    farms = (
        await session.execute(
            select(FarmMember.farm_id, FarmMember.role)
            .join(Farm, Farm.id == FarmMember.farm_id)
            .where(FarmMember.user_id == user_id, FarmMember.removed_at.is_(None), Farm.deleted_at.is_(None))
            .order_by(FarmMember.added_at)
        )
    ).all()
    records = (
        await session.execute(
            select(TrialRecord)
            .where(TrialRecord.author_id == user_id, TrialRecord.deleted_at.is_(None))
            .order_by(TrialRecord.created_at)
        )
    ).scalars().all()
    data = await _field_data(session, user_id, [(f, r) for f, r in farms])
    data.update(await _f6_data(session, user_id, [(f, r) for f, r in farms]))
    return {
        **data,
        "profile": {"phone": user.phone_e164, "display_name": user.display_name, "language": user.language},
        "consents": [
            {
                "purpose": c.purpose, "text_version": c.text_version,
                "granted_at": c.granted_at.isoformat(),
                "withdrawn_at": c.withdrawn_at.isoformat() if c.withdrawn_at else None,
            }
            for c in consents
        ],
        "farms": [{"id": str(f), "role": r} for f, r in farms],
        "records": [
            {
                "id": str(r.id), "farm_id": str(r.farm_id), "title": r.title, "note": r.note,
                "quantity": None if r.quantity is None else float(r.quantity),
                "created_at": r.created_at.isoformat(),
            }
            for r in records
        ],
    }
