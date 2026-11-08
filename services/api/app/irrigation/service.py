"""F4 writes (REST and sync share them): installation, irrigation events, water analyses, recompute scheduling.

Every quota is counted under the per-farm advisory lock, in the SAME transaction as the write, so two concurrent requests
never both take the last slot. Nothing is computed here: a recompute is only scheduled (coalesced, one active job per parcel).
Time arrives as `now` (the injected clock read by the caller).
"""
import datetime as dt
import inspect
import json
import uuid
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.farm_context import NOT_FOUND
from app.domain.application_rate import application_rate
from app.domain.clock import local_day
from app.domain.irrigation_efficiency import resolve_efficiency
from app.domain.irrigation_limits import LIMITS
from app.domain.irrigation_units import from_duration, from_volume
from app.irrigation.ids import operation_id_for
from app.irrigation.schemas import IrrigationEventInput, IrrigationSystemInput, WaterAnalysisInput

_FARM_LOCK = "SELECT pg_advisory_xact_lock(hashtextextended(CAST(:farm AS text), 0))"


class Refusal(Exception):
    """A field-level refusal: 422 `{detail: validation, field, code}`."""

    def __init__(self, field: str, code: str) -> None:
        super().__init__(code)
        self.field, self.code = field, code


class QuotaExceeded(Exception):
    """A cap reached under the farm lock: 409 `{detail: quota_exceeded, code}`."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _f(v: Any) -> float | None:
    return None if v is None else float(v)


async def lock_farm(session: AsyncSession, farm_id: uuid.UUID) -> None:
    await session.execute(text(_FARM_LOCK), {"farm": str(farm_id)})


async def schedule_recompute(session: AsyncSession, farm_id: uuid.UUID, parcel_id: uuid.UUID, from_date: dt.date) -> None:
    """One active job per parcel, keeping the OLDEST date; at most 5 active jobs per farm (QuotaExceeded beyond)."""
    await lock_farm(session, farm_id)
    key = {"f": farm_id, "p": parcel_id}
    queued = (await session.execute(text("SELECT id, from_date FROM irrigation_jobs WHERE farm_id = :f AND parcel_id = :p AND state = 'queued'"), key)).first()
    if queued is not None:
        await session.execute(text("UPDATE irrigation_jobs SET from_date = :d WHERE id = :i AND farm_id = :f"), {"d": min(from_date, queued[1]), "i": queued[0], "f": farm_id})
        return
    active = (await session.execute(text("SELECT count(*) FROM irrigation_jobs WHERE farm_id = :f AND state IN ('queued', 'running')"), {"f": farm_id})).scalar_one()
    if active >= LIMITS["jobs_per_farm"]:
        raise QuotaExceeded("jobs_per_farm")
    await session.execute(
        text("INSERT INTO irrigation_jobs (id, farm_id, parcel_id, from_date, state) VALUES (:i, :f, :p, :d, 'queued')"),
        {"i": uuid.uuid4(), "f": farm_id, "p": parcel_id, "d": from_date},
    )


async def _schedule(session: AsyncSession, farm_id: uuid.UUID, parcel_id: uuid.UUID, from_date: dt.date) -> None:
    """Schedule a recompute without ever failing the write: a real input is never lost, the nightly run covers every parcel.
    `schedule_recompute` is resolved at call time (spied on in tests) and may be a plain function."""
    try:
        outcome = schedule_recompute(session, farm_id, parcel_id, from_date)
        if inspect.isawaitable(outcome):
            await outcome
    except QuotaExceeded:
        pass


async def _parcel(session: AsyncSession, farm_id: uuid.UUID, parcel_id: uuid.UUID) -> Any:
    row = (await session.execute(
        text("SELECT p.irrigation, COALESCE(p.area_calc_ha, p.area_declared_ha, ST_Area(p.geometry::geography) / 10000.0) AS area_ha FROM parcels p WHERE p.farm_id = :f AND p.id = :p AND p.archived_at IS NULL"),
        {"f": farm_id, "p": parcel_id},
    )).first()
    if row is None:
        raise NOT_FOUND
    return row


async def _system_row(session: AsyncSession, farm_id: uuid.UUID, parcel_id: uuid.UUID) -> Any:
    return (await session.execute(
        text("SELECT id, kind, emitter_flow_lph, emitter_spacing_m, row_spacing_m, pump_flow_m3h, sectors_count, efficiency, efficiency_is_default,"
             " server_version FROM irrigation_systems WHERE farm_id = :f AND parcel_id = :p AND parcel_archived_at IS NULL"),
        {"f": farm_id, "p": parcel_id},
    )).first()


def system_json(row: Any, parcel_id: uuid.UUID, area_ha: Any) -> dict[str, Any]:
    eff = resolve_efficiency({"kind": row.kind, "efficiency": _f(row.efficiency)})
    rate = application_rate({
        "kind": row.kind, "emitter_flow_lph": _f(row.emitter_flow_lph), "emitter_spacing_m": _f(row.emitter_spacing_m),
        "row_spacing_m": _f(row.row_spacing_m), "pump_flow_m3h": _f(row.pump_flow_m3h), "sectors_count": row.sectors_count,
        "area_m2": None if area_ha is None else float(area_ha) * 10000,
    })["rate_mm_h"]
    return {
        "id": str(row.id), "parcel_id": str(parcel_id), "kind": row.kind, "emitter_flow_lph": _f(row.emitter_flow_lph),
        "emitter_spacing_m": _f(row.emitter_spacing_m), "row_spacing_m": _f(row.row_spacing_m), "pump_flow_m3h": _f(row.pump_flow_m3h),
        "sectors_count": row.sectors_count, "efficiency": _f(row.efficiency), "efficiency_effective": eff["efficiency"],
        "efficiency_is_default": bool(eff["is_default"]), "application_rate_mm_h": rate, "server_version": int(row.server_version),
    }


async def get_system(session: AsyncSession, farm_id: uuid.UUID, parcel_id: uuid.UUID) -> dict[str, Any]:
    parcel = await _parcel(session, farm_id, parcel_id)
    row = await _system_row(session, farm_id, parcel_id)
    if row is None:
        raise NOT_FOUND
    return system_json(row, parcel_id, parcel.area_ha)


async def put_system(session: AsyncSession, farm_id: uuid.UUID, user_id: uuid.UUID, parcel_id: uuid.UUID, body: IrrigationSystemInput, now: dt.datetime) -> dict[str, Any]:
    """Create or replace the active installation of a parcel and keep a version of it. A rainfed parcel refuses (422)."""
    parcel = await _parcel(session, farm_id, parcel_id)
    if parcel.irrigation == "rainfed":
        raise Refusal("parcel", "parcel_rainfed")
    await lock_farm(session, farm_id)
    existing = await _system_row(session, farm_id, parcel_id)
    versions = 0
    if existing is not None:
        versions = (await session.execute(text("SELECT count(*) FROM irrigation_system_versions WHERE farm_id = :f AND system_id = :s"), {"f": farm_id, "s": existing.id})).scalar_one()
        if versions >= LIMITS["system_versions"]:
            raise QuotaExceeded("system_versions")
    values = {
        "kind": body.kind, "e": body.emitter_flow_lph, "es": body.emitter_spacing_m, "rs": body.row_spacing_m, "pf": body.pump_flow_m3h,
        "n": body.sectors_count, "eff": body.efficiency, "isdef": body.efficiency is None, "at": now,
    }
    if existing is None:
        system_id = body.id or uuid.uuid4()
        await session.execute(
            text("INSERT INTO irrigation_systems (id, farm_id, parcel_id, kind, emitter_flow_lph, emitter_spacing_m, row_spacing_m, pump_flow_m3h,"
                 " sectors_count, efficiency, efficiency_is_default, created_at, updated_at)"
                 " VALUES (:id, :f, :p, :kind, :e, :es, :rs, :pf, :n, :eff, :isdef, :at, :at)"),
            {**values, "id": system_id, "f": farm_id, "p": parcel_id},
        )
    else:
        system_id = existing.id
        await session.execute(
            text("UPDATE irrigation_systems SET kind = :kind, emitter_flow_lph = :e, emitter_spacing_m = :es, row_spacing_m = :rs, pump_flow_m3h = :pf,"
                 " sectors_count = :n, efficiency = :eff, efficiency_is_default = :isdef, updated_at = :at, server_version = server_version + 1"
                 " WHERE id = :id AND farm_id = :f"),
            {**values, "id": system_id, "f": farm_id},
        )
    snapshot = body.model_dump(mode="json", exclude={"id"})
    await session.execute(
        text("INSERT INTO irrigation_system_versions (id, farm_id, system_id, parcel_id, snapshot, changed_by, changed_at)"
             " VALUES (:i, :f, :s, :p, CAST(:snap AS jsonb), :u, :at)"),
        {"i": uuid.uuid4(), "f": farm_id, "s": system_id, "p": parcel_id, "snap": json.dumps(snapshot), "u": user_id, "at": now},
    )
    return await get_system(session, farm_id, parcel_id)


async def list_versions(session: AsyncSession, farm_id: uuid.UUID, parcel_id: uuid.UUID, limit: int, offset: int) -> dict[str, Any]:
    rows = (await session.execute(
        text("SELECT v.id, v.snapshot, v.changed_by, v.changed_at FROM irrigation_system_versions v WHERE v.farm_id = :f AND v.parcel_id = :p"
             " ORDER BY v.changed_at DESC, v.id LIMIT :l OFFSET :o"),
        {"f": farm_id, "p": parcel_id, "l": limit, "o": offset},
    )).all()
    return {"items": [{"id": str(r.id), "snapshot": r.snapshot, "changed_by": str(r.changed_by) if r.changed_by else None, "changed_at": r.changed_at.isoformat()} for r in rows]}


# ---- irrigation events ----

def event_json(r: Any) -> dict[str, Any]:
    return {
        "id": str(r.id), "parcel_id": str(r.parcel_id), "operation_id": str(r.operation_id), "performed_on": r.performed_on.isoformat(),
        "sector_no": r.sector_no, "input_mode": r.input_mode, "duration_min": r.duration_min, "volume_m3": _f(r.volume_m3),
        "net_mm": _f(r.net_mm), "status": r.status, "author_id": str(r.author_id) if r.author_id else None, "note": r.note,
    }


_EVENT_COLS = "id, parcel_id, operation_id, performed_on, sector_no, input_mode, duration_min, volume_m3, net_mm, status, author_id, note"


async def record_event(
    session: AsyncSession, farm_id: uuid.UUID, user_id: uuid.UUID, parcel_id: uuid.UUID, body: IrrigationEventInput, now: dt.datetime
) -> tuple[dict[str, Any], bool]:
    """Returns (event, created). A replay of the same id on the same parcel is a no-op (created=False). Raises Refusal,
    QuotaExceeded or NOT_FOUND (the id belongs to another farm: no oracle)."""
    today = local_day(now)
    if body.performed_on > today:
        raise Refusal("performed_on", "in_the_future")
    if (today - body.performed_on).days > LIMITS["backdate_days"]:
        raise Refusal("performed_on", "too_old")
    parcel = await _parcel(session, farm_id, parcel_id)
    await lock_farm(session, farm_id)
    other = (await session.execute(text("SELECT farm_id, parcel_id FROM irrigation_events WHERE id = :i"), {"i": body.id})).first()
    if other is not None:
        if other.farm_id != farm_id or other.parcel_id != parcel_id:
            raise NOT_FOUND
        again = (await session.execute(text(f"SELECT {_EVENT_COLS} FROM irrigation_events WHERE farm_id = :f AND id = :i"), {"f": farm_id, "i": body.id})).one()
        return event_json(again), False
    same_slot = "FROM irrigation_events WHERE farm_id = :f AND parcel_id = :p AND performed_on = :d AND sector_no IS NOT DISTINCT FROM :s AND status = 'done'"
    slot = {"f": farm_id, "p": parcel_id, "d": body.performed_on, "s": body.sector_no}
    taken = (await session.execute(text(f"SELECT count(*) {same_slot}"), slot)).scalar_one()
    if taken >= LIMITS["events_per_day_sector"]:
        raise QuotaExceeded("events_per_day_sector")
    system = await _system_row(session, farm_id, parcel_id)
    area_ha = None if parcel.area_ha is None else float(parcel.area_ha)
    if body.volume_m3 is not None and area_ha is not None and body.volume_m3 > area_ha * LIMITS["volume_m3_per_ha"]:
        raise Refusal("volume_m3", "above_cap")
    minutes, volume, net = body.duration_min, body.volume_m3, None
    if system is not None:
        info = system_json(system, parcel_id, parcel.area_ha)
        sector_area = None if area_ha is None else area_ha * 10000 / (system.sectors_count if body.sector_no is not None else 1)
        common = {"rate_mm_h": info["application_rate_mm_h"], "area_m2": sector_area, "efficiency": info["efficiency_effective"]}
        if body.duration_min is not None:
            derived = from_duration({"minutes": body.duration_min, **common})
            volume, net = derived["volume_m3"], derived["net_mm"]
        elif body.volume_m3 is not None:
            derived = from_volume({"volume_m3": body.volume_m3, **common})
            minutes, net = derived["minutes"], derived["net_mm"]
            minutes = minutes if minutes is not None and 1 <= minutes <= LIMITS["duration_min"] else None
    season = (await session.execute(text("SELECT id FROM seasons WHERE farm_id = :f AND field_id = :p AND ended_at IS NULL ORDER BY started_at DESC LIMIT 1"), {"f": farm_id, "p": parcel_id})).first()
    season_id = season[0] if season else None
    operation_id = operation_id_for(farm_id, body.id)
    await session.execute(
        text("INSERT INTO operations (id, farm_id, type, performed_on, status, author_id, season_id, done_at, created_at, updated_at)"
             " VALUES (:o, :f, 'irrigation', :d, 'done', :u, :s, :at, :at, :at)"),
        {"o": operation_id, "f": farm_id, "d": body.performed_on, "u": user_id, "s": season_id, "at": now},
    )
    await session.execute(
        text("INSERT INTO operation_parcels (id, farm_id, operation_id, parcel_id, author_id, type, performed_on, status, area_ha_snapshot, updated_at)"
             " VALUES (:i, :f, :o, :p, :u, 'irrigation', :d, 'done', :a, :at)"),
        {"i": uuid.uuid4(), "f": farm_id, "o": operation_id, "p": parcel_id, "u": user_id, "d": body.performed_on, "a": parcel.area_ha, "at": now},
    )
    mode = "duration" if body.duration_min is not None else "volume"
    await session.execute(
        text("INSERT INTO irrigation_events (id, farm_id, parcel_id, season_id, operation_id, performed_on, sector_no, input_mode, duration_min,"
             " volume_m3, net_mm, author_id, note, status, created_at, updated_at)"
             " VALUES (:i, :f, :p, :s, :o, :d, :sector, :mode, :min, :vol, :net, :u, :note, 'done', :at, :at)"),
        {"i": body.id, "f": farm_id, "p": parcel_id, "s": season_id, "o": operation_id, "d": body.performed_on, "sector": body.sector_no,
         "mode": mode, "min": minutes, "vol": None if volume is None else Decimal(repr(round(volume, 4))),
         "net": None if net is None else Decimal(repr(round(net, 4))), "u": user_id, "note": body.note or None, "at": now},
    )
    await _schedule(session, farm_id, parcel_id, body.performed_on)
    row = (await session.execute(text(f"SELECT {_EVENT_COLS} FROM irrigation_events WHERE farm_id = :f AND id = :i"), {"f": farm_id, "i": body.id})).one()
    out = event_json(row)
    out["possible_duplicate"] = (await session.execute(text(f"SELECT count(*) {same_slot} AND id <> :i"), {**slot, "i": body.id})).scalar_one() > 0
    return out, True


async def cancel_event(session: AsyncSession, farm_id: uuid.UUID, user_id: uuid.UUID, role: str, parcel_id: uuid.UUID, event_id: uuid.UUID, now: dt.datetime) -> dict[str, Any]:
    """done -> cancelled, never a delete; the linked F6 operation is cancelled with it. A worker may only cancel their own."""
    await lock_farm(session, farm_id)
    row = (await session.execute(
        text(f"SELECT {_EVENT_COLS} FROM irrigation_events WHERE farm_id = :f AND parcel_id = :p AND id = :i"), {"f": farm_id, "p": parcel_id, "i": event_id},
    )).first()
    if row is None:
        raise NOT_FOUND
    if role == "worker" and row.author_id != user_id:
        raise HTTPException(status_code=403, detail="forbidden")
    if row.status == "cancelled":
        return event_json(row)
    await session.execute(
        text("UPDATE irrigation_events SET status = 'cancelled', updated_at = :at, server_version = server_version + 1 WHERE id = :i AND farm_id = :f"),
        {"i": event_id, "f": farm_id, "at": now},
    )
    await session.execute(text("UPDATE operation_parcels SET status = 'cancelled', updated_at = :at WHERE farm_id = :f AND operation_id = :o"), {"f": farm_id, "o": row.operation_id, "at": now})
    await session.execute(text("UPDATE operations SET status = 'cancelled', updated_at = :at WHERE farm_id = :f AND id = :o"), {"f": farm_id, "o": row.operation_id, "at": now})
    await _schedule(session, farm_id, parcel_id, row.performed_on)
    done = (await session.execute(text(f"SELECT {_EVENT_COLS} FROM irrigation_events WHERE farm_id = :f AND id = :i"), {"f": farm_id, "i": event_id})).one()
    return event_json(done)


async def list_events(session: AsyncSession, farm_id: uuid.UUID, user_id: uuid.UUID, role: str, parcel_id: uuid.UUID, limit: int, offset: int) -> dict[str, Any]:
    """A worker sees their own events only."""
    mine = " AND author_id = :u" if role == "worker" else ""
    rows = (await session.execute(
        text(f"SELECT {_EVENT_COLS} FROM irrigation_events WHERE farm_id = :f AND parcel_id = :p{mine} ORDER BY performed_on DESC, id LIMIT :l OFFSET :o"),
        {"f": farm_id, "p": parcel_id, "u": user_id, "l": limit + 1, "o": offset},
    )).all()
    return {"items": [event_json(r) for r in rows[:limit]], "next_cursor": str(offset + limit) if len(rows) > limit else None}


# ---- water analyses (staff only) ----

def analysis_json(r: Any, today: dt.date) -> dict[str, Any]:
    return {"id": str(r.id), "parcel_id": str(r.parcel_id), "ec_ds_m": float(r.ec_ds_m), "analysed_on": r.analysed_on.isoformat(),
            "water_source": r.water_source or "", "age_days": (today - r.analysed_on).days}


async def add_analysis(session: AsyncSession, farm_id: uuid.UUID, user_id: uuid.UUID, parcel_id: uuid.UUID, body: WaterAnalysisInput, now: dt.datetime) -> tuple[dict[str, Any], bool]:
    today = local_day(now)
    if body.analysed_on > today:
        raise Refusal("analysed_on", "in_the_future")
    await _parcel(session, farm_id, parcel_id)
    await lock_farm(session, farm_id)
    cols = "id, parcel_id, ec_ds_m, analysed_on, water_source"
    other = (await session.execute(text("SELECT farm_id, parcel_id FROM water_analyses WHERE id = :i"), {"i": body.id})).first()
    if other is not None:
        if other.farm_id != farm_id or other.parcel_id != parcel_id:
            raise NOT_FOUND
        again = (await session.execute(text(f"SELECT {cols} FROM water_analyses WHERE farm_id = :f AND id = :i"), {"f": farm_id, "i": body.id})).one()
        return analysis_json(again, today), False
    n = (await session.execute(text("SELECT count(*) FROM water_analyses WHERE farm_id = :f AND parcel_id = :p AND status = 'active'"), {"f": farm_id, "p": parcel_id})).scalar_one()
    if n >= LIMITS["water_analyses"]:
        raise QuotaExceeded("water_analyses")
    await session.execute(
        text("INSERT INTO water_analyses (id, farm_id, parcel_id, water_source, ec_ds_m, analysed_on, author_id, created_at, updated_at)"
             " VALUES (:i, :f, :p, :w, :ec, :d, :u, :at, :at)"),
        {"i": body.id, "f": farm_id, "p": parcel_id, "w": body.water_source or None, "ec": Decimal(repr(body.ec_ds_m)), "d": body.analysed_on, "u": user_id, "at": now},
    )
    row = (await session.execute(text(f"SELECT {cols} FROM water_analyses WHERE farm_id = :f AND id = :i"), {"f": farm_id, "i": body.id})).one()
    return analysis_json(row, today), True


async def list_analyses(session: AsyncSession, farm_id: uuid.UUID, parcel_id: uuid.UUID, today: dt.date, limit: int, offset: int) -> dict[str, Any]:
    rows = (await session.execute(
        text("SELECT id, parcel_id, ec_ds_m, analysed_on, water_source FROM water_analyses WHERE farm_id = :f AND parcel_id = :p AND parcel_archived_at IS NULL"
             " ORDER BY analysed_on DESC, id LIMIT :l OFFSET :o"),
        {"f": farm_id, "p": parcel_id, "l": limit + 1, "o": offset},
    )).all()
    return {"items": [analysis_json(r, today) for r in rows[:limit]], "next_cursor": str(offset + limit) if len(rows) > limit else None}
