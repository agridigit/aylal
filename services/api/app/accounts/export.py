"""Complete personal-data export (FR-026): only what belongs to the user, never hashes or others' data."""
import uuid
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.farm_context import FarmContext
from app.db.models import Consent, Farm, FarmMember, TrialRecord, User
from app.monitoring.access import visible_parcels
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


async def _f3_data(session: AsyncSession, user_id: uuid.UUID, roles: list[tuple[uuid.UUID, str]]) -> dict[str, Any]:
    """F3: monitoring data on the caller's scope. A worker gets the parcels `visible_parcels` gives (assigned, not archived)
    and the observations they wrote; staff get the whole farm, archived parcels included (read-only history). Storage keys
    and other members' push tokens never leave."""
    scope_farms: list[uuid.UUID] = []  # farms read as a whole (staff)
    scope_parcels: list[uuid.UUID] = []  # parcels read one by one (worker)
    for farm_id, role in roles:
        if role == "worker":
            scope_parcels += await visible_parcels(FarmContext(farm_id, user_id, role, session))
        else:
            scope_farms.append(farm_id)
    params = {"u": user_id, "farms": scope_farms, "parcels": scope_parcels, "all_farms": [f for f, _ in roles]}
    where = "(t.farm_id = ANY(:farms) OR t.parcel_id = ANY(:parcels))"

    async def rows(sql: str) -> list[dict[str, Any]]:
        return [r[0] for r in (await session.execute(text(f"SELECT to_jsonb(q) FROM ({sql}) q"), params)).all()]

    return {
        "farm_weather": await rows("SELECT t.farm_id, t.fetched_at, t.availability, t.reason, t.days FROM farm_weather t WHERE t.farm_id = ANY(:all_farms)"),
        "alerts": await rows(
            "SELECT t.id, t.farm_id, t.parcel_id, t.crop_slug, t.type, t.severity, t.status, t.forecast_day, t.reason_key, t.reason_params,"
            f" t.advice_key, t.notify_at, t.revision, t.created_at FROM alerts t WHERE {where} ORDER BY t.forecast_day, t.id"
        ),
        "parcel_status": await rows(
            "SELECT t.parcel_id, t.farm_id, t.color, t.reason_key, t.reason_params, t.computed_at, t.imagery_reliability"
            f" FROM parcel_status t WHERE {where.replace('t.farm_id = ANY(:farms)', 't.farm_id = ANY(:farms) AND t.parcel_archived_at IS NULL')} ORDER BY t.parcel_id"
        ),
        "parcel_status_items": await rows(
            f"SELECT t.id, t.farm_id, t.parcel_id, t.source, t.severity, t.reason_key, t.observed_at FROM parcel_status_items t WHERE {where} ORDER BY t.id"
        ),
        "parcel_vigor_points": await rows(
            "SELECT t.id, t.farm_id, t.parcel_id, t.scene_id, t.acquired_on, t.vigor_mean, t.plant_moisture_mean, t.clear_pct"
            f" FROM parcel_vigor_points t WHERE t.valid AND {where} ORDER BY t.acquired_on, t.id"
        ),
        "vigor_maps": await rows(f"SELECT t.id, t.farm_id, t.parcel_id, t.scene_id, t.acquired_on, t.bounds FROM vigor_maps t WHERE {where} ORDER BY t.id"),
        "attention_zones": await rows(
            "SELECT t.id, t.farm_id, t.parcel_id, ST_AsGeoJSON(t.geometry)::json AS geometry, t.detected_on, t.area_ha::float8 AS area_ha, t.status, t.reason_key"
            f" FROM attention_zones t WHERE {where} ORDER BY t.id"
        ),
        "zone_observations": await rows(
            "SELECT t.id, t.farm_id, t.zone_id, t.parcel_id, t.author_id, t.note, (t.photo_key IS NOT NULL) AS has_photo, t.created_at"
            " FROM zone_observations t WHERE ((t.farm_id = ANY(:farms)) OR (t.parcel_id = ANY(:parcels) AND t.author_id = :u)) ORDER BY t.created_at, t.id"
        ),
        "daily_summaries": await rows(
            "SELECT t.id, t.farm_id, t.user_id, t.summary_date, t.locale, t.payload FROM daily_summaries t"
            " WHERE t.user_id = :u AND t.farm_id = ANY(:all_farms) ORDER BY t.summary_date, t.id"
        ),
        "notification_prefs": await rows(
            "SELECT t.farm_id, t.user_id, t.summary_hour, t.alerts_enabled, t.push_token FROM notification_prefs t"
            " WHERE t.user_id = :u AND t.farm_id = ANY(:all_farms) ORDER BY t.farm_id"
        ),
    }


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
        "monitoring": await _f3_data(session, user_id, [(f, r) for f, r in farms]),
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
