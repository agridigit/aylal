"""F2 data access and write rules shared by the REST routers and the sync layer.

Every function runs inside the caller's transaction, loads child objects with farm_id in the WHERE
clause and raises FieldError (never leaks another farm's data). Server-owned columns
(farm_id of an existing row, area_calc_ha, status_summary, created_by, archived_at, purge_after)
are only ever written here, from trusted values.
"""
import datetime as dt
import json
import uuid
from collections.abc import Mapping
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.field_rules import LIMITS as FIELD_LIMITS
from app.domain.geometry import centroid, is_in_morocco
from app.domain.season_rules import estimate_stage
from app.domain.field_limits import (
    BLOCK_KINDS,
    CYCLES,
    IRRIGATIONS,
    MAX_VERTICES,
    MIN_VERTICES,
    SOURCES,
    purge_after,
    season_dates_error,
    valid_name,
)

Data = Mapping[str, Any]
FIELD_COLS = (
    "id, farm_id, name, ST_AsGeoJSON(geometry)::json AS geometry, area_calc_ha::float8 AS area_calc_ha, area_declared_ha::float8 AS area_declared_ha, irrigation,"
    " greenhouse, soil, source, gps_accuracy_m, status_summary, created_by, archived_at, purge_after,"
    " merged_into_id, server_version, updated_at"
)
BLOCK_COLS = (
    "id, farm_id, field_id, name, kind, ST_AsGeoJSON(geometry)::json AS geometry, area_calc_ha::float8 AS area_calc_ha,"
    " archived_at, server_version, updated_at"
)
SEASON_COLS = (
    "id, farm_id, field_id, crop_id, variety, planting_year, sowing_date, started_at, ended_at,"
    " stage_estimated, stage_corrected, stage_corrected_at, destination, server_version, updated_at"
)
CROP_COLS = (
    "id, farm_id, slug, name_ary, name_ar, name_fr, cycle, photo_key, varieties, stages, has_agronomy,"
    " validated, archived_at"
)


class FieldError(Exception):
    def __init__(self, status: int, code: str, field: str | None = None) -> None:
        super().__init__(code)
        self.status, self.code, self.field = status, code, field


def _bad(field: str, code: str = "validation") -> FieldError:
    return FieldError(422, code, field)


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


async def _one(session: AsyncSession, sql: str, **params: Any) -> dict[str, Any] | None:
    row = (await session.execute(text(sql), params)).mappings().first()
    return dict(row) if row else None


# ---------- validation helpers ----------

def _date(data: Data, key: str, required: bool = False) -> dt.date | None:
    value = data.get(key)
    if value is None:
        if required:
            raise _bad(key)
        return None
    if isinstance(value, dt.date):
        return value
    try:
        return dt.date.fromisoformat(str(value)[:10])
    except ValueError:
        raise _bad(key) from None


def _number(data: Data, key: str, positive: bool = True) -> float | None:
    value = data.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float) or (positive and value <= 0):
        raise _bad(key)
    return float(value)


async def check_polygon(session: AsyncSession, geojson: object, field: str = "geometry") -> str:
    """Structural check in Python (so PostGIS never raises), then validity/simplicity/area in PostGIS."""
    if not isinstance(geojson, dict) or geojson.get("type") != "Polygon":
        raise _bad(field, "geometry_invalid")
    rings = geojson.get("coordinates")
    if not isinstance(rings, list) or len(rings) != 1 or not isinstance(rings[0], list):
        raise _bad(field, "geometry_invalid")
    ring = rings[0]
    for pos in ring:
        ok = isinstance(pos, list) and len(pos) == 2 and all(isinstance(c, int | float) and not isinstance(c, bool) for c in pos)
        if not ok or not (-180 <= pos[0] <= 180 and -90 <= pos[1] <= 90):
            raise _bad(field, "geometry_invalid")
    if len(ring) < 4 or ring[0] != ring[-1]:
        raise _bad(field, "geometry_too_few_points")
    if len(ring) - 1 > MAX_VERTICES or len(ring) - 1 < MIN_VERTICES:
        raise _bad(field, "geometry_vertices")
    if not is_in_morocco(centroid(ring)):
        raise _bad(field, "outside_morocco")
    payload = json.dumps(geojson)
    row = await _one(
        session,
        "SELECT ST_IsValid(g) AS valid, ST_Area(g::geography) / 10000 AS ha"
        " FROM (SELECT ST_SetSRID(ST_GeomFromGeoJSON(CAST(:g AS text)), 4326) AS g) t",
        g=payload,
    )
    assert row is not None
    if not row["valid"]:
        raise _bad(field, "geometry_self_intersecting")
    if row["ha"] <= 0:
        raise _bad(field, "geometry_area_zero")
    if row["ha"] > FIELD_LIMITS["MAX_AREA_HA"]:
        raise _bad(field, "area_too_large")
    return payload


def _common_field_values(data: Data) -> dict[str, Any]:
    """Validated optional attributes present in `data` (user-writable columns only)."""
    out: dict[str, Any] = {}
    if "name" in data:
        if not valid_name(data["name"]):
            raise _bad("name")
        out["name"] = data["name"].strip()
    if "irrigation" in data:
        if data["irrigation"] is not None and data["irrigation"] not in IRRIGATIONS:
            raise _bad("irrigation")
        out["irrigation"] = data["irrigation"]
    if "greenhouse" in data:
        if not isinstance(data["greenhouse"], bool):
            raise _bad("greenhouse")
        out["greenhouse"] = data["greenhouse"]
    if "soil" in data:
        if data["soil"] is not None and not (isinstance(data["soil"], str) and len(data["soil"]) <= 80):
            raise _bad("soil")
        out["soil"] = data["soil"]
    if "area_declared_ha" in data:
        out["area_declared_ha"] = _number(data, "area_declared_ha")
    if "gps_accuracy_m" in data:
        out["gps_accuracy_m"] = _number(data, "gps_accuracy_m", positive=False)
    if "source" in data:
        if data["source"] not in SOURCES:
            raise _bad("source")
        out["source"] = data["source"]
    return out


# ---------- fields ----------

async def get_field(session: AsyncSession, farm_id: uuid.UUID, field_id: uuid.UUID, *, archived: bool = False) -> dict[str, Any]:
    cond = "IS NOT NULL" if archived else "IS NULL"
    row = await _one(
        session, f"SELECT {FIELD_COLS} FROM parcels WHERE id = :i AND farm_id = :f AND archived_at {cond}", i=field_id, f=farm_id
    )
    if row is None:
        raise FieldError(404, "not_found")
    return row


async def overlap_warnings(session: AsyncSession, farm_id: uuid.UUID, field_id: uuid.UUID) -> list[dict[str, str]]:
    rows = (
        await session.execute(
            text(
                "SELECT o.id FROM parcels p JOIN parcels o ON o.farm_id = p.farm_id AND o.id <> p.id"
                " AND o.archived_at IS NULL AND ST_Intersects(o.geometry, p.geometry)"
                " AND ST_Area(ST_Intersection(o.geometry, p.geometry)) > 0"
                " WHERE p.id = :i AND p.farm_id = :f"
            ),
            {"i": field_id, "f": farm_id},
        )
    ).all()
    return [{"code": "overlap", "field_id": str(r[0])} for r in rows]


async def _lock_farm_fields(session: AsyncSession, farm_id: uuid.UUID) -> None:
    """Serialise field creation/restoration per farm until the transaction ends (500 cap)."""
    await session.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(CAST(:f AS text), 0))"), {"f": str(farm_id)})


async def _check_field_cap(session: AsyncSession, farm_id: uuid.UUID) -> None:
    await _lock_farm_fields(session, farm_id)
    count = await _one(session, "SELECT count(*) AS n FROM parcels WHERE farm_id = :f AND archived_at IS NULL", f=farm_id)
    assert count is not None
    if count["n"] >= FIELD_LIMITS["MAX_FIELDS_PER_FARM"]:
        raise _bad("geometry", "field_limit_reached")


async def create_field(
    session: AsyncSession, farm_id: uuid.UUID, user_id: uuid.UUID, data: Data, field_id: uuid.UUID | None = None
) -> dict[str, Any]:
    values = _common_field_values(data)
    if "name" not in values:
        raise _bad("name")
    geometry = await check_polygon(session, data.get("geometry"))
    await _check_field_cap(session, farm_id)
    field_id = field_id or uuid.uuid4()
    values.setdefault("greenhouse", False)
    values.setdefault("source", "draw_taps")
    cols = ", ".join(values)
    marks = ", ".join(f":{k}" for k in values)
    await session.execute(
        text(
            f"INSERT INTO parcels (id, farm_id, created_by, geometry, area_calc_ha, {cols})"
            " SELECT :id, :farm, :uid, g, ROUND((ST_Area(g::geography) / 10000)::numeric, 4), "
            f"{marks} FROM (SELECT ST_SetSRID(ST_GeomFromGeoJSON(CAST(:g AS text)), 4326) AS g) t"
        ),
        {"id": field_id, "farm": farm_id, "uid": user_id, "g": geometry, **values},
    )
    return {**await get_field(session, farm_id, field_id), "warnings": await overlap_warnings(session, farm_id, field_id)}


async def update_field(session: AsyncSession, farm_id: uuid.UUID, field_id: uuid.UUID, data: Data) -> dict[str, Any]:
    await get_field(session, farm_id, field_id)
    values = _common_field_values(data)
    sets = [f"{k} = :{k}" for k in values]
    params: dict[str, Any] = {"i": field_id, "f": farm_id, **values}
    if "geometry" in data:
        params["g"] = await check_polygon(session, data["geometry"])
        sets += [
            "geometry = ST_SetSRID(ST_GeomFromGeoJSON(CAST(:g AS text)), 4326)",
            "area_calc_ha = ROUND((ST_Area(ST_SetSRID(ST_GeomFromGeoJSON(CAST(:g AS text)), 4326)::geography) / 10000)::numeric, 4)",
        ]
    if sets:
        await session.execute(
            text(f"UPDATE parcels SET {', '.join(sets)}, server_version = server_version + 1, updated_at = now() WHERE id = :i AND farm_id = :f"),
            params,
        )
    return {**await get_field(session, farm_id, field_id), "warnings": await overlap_warnings(session, farm_id, field_id)}


async def _set_children_state(session: AsyncSession, farm_id: uuid.UUID, field_ids: list[uuid.UUID], state: dt.datetime | None) -> None:
    for table in ("seasons", "field_blocks"):
        await session.execute(
            text(f"UPDATE {table} SET parcel_archived_at = :s WHERE farm_id = :f AND field_id = ANY(:ids)"),
            {"s": state, "f": farm_id, "ids": field_ids},
        )


async def archive_field(session: AsyncSession, farm_id: uuid.UUID, field_id: uuid.UUID, merged_into: uuid.UUID | None = None) -> None:
    await get_field(session, farm_id, field_id)
    now = _now()
    await session.execute(
        text(
            "UPDATE parcels SET archived_at = :a, purge_after = :p, merged_into_id = :m,"
            " server_version = server_version + 1, updated_at = now() WHERE id = :i AND farm_id = :f"
        ),
        {"a": now, "p": purge_after(now), "m": merged_into, "i": field_id, "f": farm_id},
    )
    await _set_children_state(session, farm_id, [field_id], now)  # same transaction as the parent


async def restore_field(session: AsyncSession, farm_id: uuid.UUID, field_id: uuid.UUID) -> dict[str, Any]:
    row = await get_field(session, farm_id, field_id, archived=True)
    if row["purge_after"] is not None and row["purge_after"] <= _now():
        raise FieldError(404, "not_found")
    await _check_field_cap(session, farm_id)
    await session.execute(
        text(
            "UPDATE parcels SET archived_at = NULL, purge_after = NULL, merged_into_id = NULL,"
            " server_version = server_version + 1, updated_at = now() WHERE id = :i AND farm_id = :f"
        ),
        {"i": field_id, "f": farm_id},
    )
    await _set_children_state(session, farm_id, [field_id], None)
    return await get_field(session, farm_id, field_id)


async def _move_children(session: AsyncSession, farm_id: uuid.UUID, survivor: uuid.UUID, merged: list[uuid.UUID]) -> None:
    """Seasons, blocks and worker assignments follow the survivor; a duplicate active crop keeps the oldest season."""
    ids = [survivor, *merged]
    await session.execute(
        text(
            "UPDATE seasons SET ended_at = GREATEST(CURRENT_DATE, started_at), server_version = server_version + 1, updated_at = now()"
            " WHERE farm_id = :f AND field_id = ANY(:ids) AND ended_at IS NULL AND id NOT IN ("
            "  SELECT DISTINCT ON (crop_id) id FROM seasons WHERE farm_id = :f AND field_id = ANY(:ids) AND ended_at IS NULL"
            "  ORDER BY crop_id, started_at, id)"
        ),
        {"f": farm_id, "ids": ids},
    )
    for table in ("seasons", "field_blocks"):
        await session.execute(
            text(
                f"UPDATE {table} SET field_id = :s, parcel_archived_at = NULL, server_version = server_version + 1, updated_at = now()"
                " WHERE farm_id = :f AND field_id = ANY(:m)"
            ),
            {"s": survivor, "f": farm_id, "m": merged},
        )
    await session.execute(
        text(
            "INSERT INTO worker_parcels (farm_id, user_id, parcel_id) SELECT DISTINCT farm_id, user_id, CAST(:s AS uuid) FROM worker_parcels"
            " WHERE farm_id = :f AND parcel_id = ANY(:m) ON CONFLICT DO NOTHING"
        ),
        {"s": survivor, "f": farm_id, "m": merged},
    )
    await session.execute(text("DELETE FROM worker_parcels WHERE farm_id = :f AND parcel_id = ANY(:m)"), {"f": farm_id, "m": merged})


async def merge_fields(session: AsyncSession, farm_id: uuid.UUID, survivor_id: Any, merged_ids: Any) -> dict[str, Any]:
    try:
        survivor = uuid.UUID(str(survivor_id))
        merged = [uuid.UUID(str(m)) for m in (merged_ids if isinstance(merged_ids, list) else [None])]
    except ValueError:
        raise _bad("merged_ids") from None
    ids = [survivor, *merged]
    found = (await session.execute(
        text("SELECT id FROM parcels WHERE farm_id = :f AND archived_at IS NULL AND id = ANY(:ids)"), {"f": farm_id, "ids": ids}
    )).all()
    if len({r[0] for r in found}) != len(set(ids)):
        raise FieldError(404, "not_found")  # unknown, other farm or archived: indistinguishable
    if len(set(ids)) != len(ids) or not merged:
        raise _bad("merged_ids", "merge_needs_two_fields")
    union = await _one(
        session,
        "SELECT ST_AsGeoJSON(u) AS g, GeometryType(u) AS t FROM (SELECT ST_UnaryUnion(ST_Collect(geometry)) AS u"
        " FROM parcels WHERE farm_id = :f AND id = ANY(:ids)) t",
        f=farm_id, ids=ids,
    )
    assert union is not None
    if union["t"] != "POLYGON":
        raise _bad("merged_ids", "merge_not_contiguous")
    await session.execute(
        text(
            "UPDATE parcels SET geometry = ST_SetSRID(ST_GeomFromGeoJSON(CAST(:g AS text)), 4326),"
            " area_calc_ha = ROUND((ST_Area(ST_SetSRID(ST_GeomFromGeoJSON(CAST(:g AS text)), 4326)::geography) / 10000)::numeric, 4),"
            " server_version = server_version + 1, updated_at = now() WHERE id = :i AND farm_id = :f"
        ),
        {"g": union["g"], "i": survivor, "f": farm_id},
    )
    await _move_children(session, farm_id, survivor, merged)
    for m in merged:
        await archive_field(session, farm_id, m, merged_into=survivor)
    return await get_field(session, farm_id, survivor)


# ---------- blocks ----------

async def get_block(session: AsyncSession, farm_id: uuid.UUID, field_id: uuid.UUID, block_id: uuid.UUID) -> dict[str, Any]:
    row = await _one(
        session,
        f"SELECT {BLOCK_COLS} FROM field_blocks WHERE id = :i AND farm_id = :f AND field_id = :fi AND archived_at IS NULL",
        i=block_id, f=farm_id, fi=field_id,
    )
    if row is None:
        raise FieldError(404, "not_found")
    return row


async def _check_block_geometry(session: AsyncSession, farm_id: uuid.UUID, field_id: uuid.UUID, geometry: str, own: uuid.UUID | None) -> None:
    row = await _one(
        session,
        "WITH b AS (SELECT ST_SetSRID(ST_GeomFromGeoJSON(CAST(:g AS text)), 4326) AS g)"
        " SELECT (SELECT ST_Area(ST_Difference(b.g, p.geometry)) / ST_Area(b.g) > 0.01 FROM parcels p, b"
        "         WHERE p.id = :fi AND p.farm_id = :f) AS outside,"
        "        EXISTS (SELECT 1 FROM field_blocks o, b WHERE o.farm_id = :f AND o.field_id = :fi"
        "                AND o.archived_at IS NULL AND o.id IS DISTINCT FROM CAST(:own AS uuid)"
        "                AND ST_Area(ST_Intersection(o.geometry, b.g)) / ST_Area(b.g) > 0.01) AS overlap",
        g=geometry, fi=field_id, f=farm_id, own=own,
    )
    assert row is not None
    if row["outside"]:
        raise _bad("geometry", "block_outside_field")
    if row["overlap"]:
        raise _bad("geometry", "block_overlap")


def _block_values(data: Data) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if "name" in data:
        if not valid_name(data["name"]):
            raise _bad("name")
        out["name"] = data["name"].strip()
    if "kind" in data:
        if data["kind"] not in BLOCK_KINDS:
            raise _bad("kind")
        out["kind"] = data["kind"]
    return out


async def create_block(session: AsyncSession, farm_id: uuid.UUID, field_id: uuid.UUID, data: Data, block_id: uuid.UUID | None = None) -> dict[str, Any]:
    values = _block_values(data)
    if "name" not in values or "kind" not in values:
        raise _bad("name" if "name" not in values else "kind")
    geometry = await check_polygon(session, data.get("geometry"))
    block_id = block_id or uuid.uuid4()
    await _check_block_geometry(session, farm_id, field_id, geometry, block_id)
    await session.execute(
        text(
            "INSERT INTO field_blocks (id, farm_id, field_id, name, kind, geometry, area_calc_ha)"
            " SELECT :id, :f, :fi, :name, :kind, g, ROUND((ST_Area(g::geography) / 10000)::numeric, 4)"
            " FROM (SELECT ST_SetSRID(ST_GeomFromGeoJSON(CAST(:g AS text)), 4326) AS g) t"
        ),
        {"id": block_id, "f": farm_id, "fi": field_id, "g": geometry, **values},
    )
    return await get_block(session, farm_id, field_id, block_id)


async def update_block(session: AsyncSession, farm_id: uuid.UUID, field_id: uuid.UUID, block_id: uuid.UUID, data: Data) -> dict[str, Any]:
    await get_block(session, farm_id, field_id, block_id)
    values = _block_values(data)
    sets = [f"{k} = :{k}" for k in values]
    params: dict[str, Any] = {"i": block_id, "f": farm_id, **values}
    if "geometry" in data:
        params["g"] = await check_polygon(session, data["geometry"])
        await _check_block_geometry(session, farm_id, field_id, params["g"], block_id)
        sets += [
            "geometry = ST_SetSRID(ST_GeomFromGeoJSON(CAST(:g AS text)), 4326)",
            "area_calc_ha = ROUND((ST_Area(ST_SetSRID(ST_GeomFromGeoJSON(CAST(:g AS text)), 4326)::geography) / 10000)::numeric, 4)",
        ]
    if sets:
        await session.execute(
            text(f"UPDATE field_blocks SET {', '.join(sets)}, server_version = server_version + 1, updated_at = now() WHERE id = :i AND farm_id = :f"),
            params,
        )
    return await get_block(session, farm_id, field_id, block_id)


async def delete_block(session: AsyncSession, farm_id: uuid.UUID, field_id: uuid.UUID, block_id: uuid.UUID) -> None:
    await get_block(session, farm_id, field_id, block_id)
    await session.execute(text("DELETE FROM field_blocks WHERE id = :i AND farm_id = :f"), {"i": block_id, "f": farm_id})


# ---------- crops ----------

async def get_crop(session: AsyncSession, farm_id: uuid.UUID, crop_id: Any) -> dict[str, Any]:
    """Reference crop or free crop of THIS farm; anything else is a 404."""
    try:
        cid = uuid.UUID(str(crop_id))
    except ValueError:
        raise FieldError(404, "not_found") from None
    row = await _one(
        session,
        f"SELECT {CROP_COLS} FROM crops WHERE id = :i AND (farm_id IS NULL OR farm_id = :f) AND archived_at IS NULL",
        i=cid, f=farm_id,
    )
    if row is None:
        raise FieldError(404, "not_found")
    return row


async def list_crops(session: AsyncSession, farm_id: uuid.UUID | None) -> list[dict[str, Any]]:
    rows = (await session.execute(
        text(f"SELECT {CROP_COLS} FROM crops WHERE archived_at IS NULL AND (farm_id IS NULL OR farm_id = :f) ORDER BY farm_id NULLS FIRST, slug"),
        {"f": farm_id},
    )).mappings().all()
    return [dict(r) for r in rows]


def _crop_names(data: Data) -> dict[str, str]:
    names = {k: data[k] for k in ("name_ary", "name_ar", "name_fr") if k in data}
    if "name" in data:
        names = {**{k: data["name"] for k in ("name_ary", "name_ar", "name_fr")}, **names}
    if not names:
        raise _bad("name")
    if any(not valid_name(v) for v in names.values()):
        raise _bad("name")
    fallback = next(iter(names.values())).strip()
    return {k: names.get(k, fallback).strip() for k in ("name_ary", "name_ar", "name_fr")}


async def create_crop(session: AsyncSession, farm_id: uuid.UUID, user_id: uuid.UUID, data: Data, crop_id: uuid.UUID | None = None) -> dict[str, Any]:
    names = _crop_names(data)
    if data.get("cycle") not in CYCLES:
        raise _bad("cycle")
    crop_id = crop_id or uuid.uuid4()
    await session.execute(
        text(
            "INSERT INTO crops (id, farm_id, slug, name_ary, name_ar, name_fr, cycle, created_by)"
            " VALUES (:id, :f, :slug, :ary, :ar, :fr, :cycle, :uid)"
        ),
        {"id": crop_id, "f": farm_id, "slug": f"custom-{crop_id}", "ary": names["name_ary"], "ar": names["name_ar"],
         "fr": names["name_fr"], "cycle": data["cycle"], "uid": user_id},
    )
    return await get_crop(session, farm_id, crop_id)


async def update_crop(session: AsyncSession, farm_id: uuid.UUID, crop_id: uuid.UUID, data: Data) -> dict[str, Any]:
    crop = await get_crop(session, farm_id, crop_id)
    if crop["farm_id"] is None:
        raise FieldError(403, "forbidden")  # the shared reference is read-only
    names = _crop_names(data) if any(k in data for k in ("name", "name_ary", "name_ar", "name_fr")) else {}
    sets = [f"{k} = :{k}" for k in names]
    if sets:
        await session.execute(
            text(f"UPDATE crops SET {', '.join(sets)}, server_version = server_version + 1, updated_at = now() WHERE id = :i AND farm_id = :f"),
            {"i": crop_id, "f": farm_id, **names},
        )
    return await get_crop(session, farm_id, crop_id)


async def archive_crop(session: AsyncSession, farm_id: uuid.UUID, crop_id: uuid.UUID) -> None:
    crop = await get_crop(session, farm_id, crop_id)
    if crop["farm_id"] is None:
        raise FieldError(403, "forbidden")
    await session.execute(text("UPDATE crops SET archived_at = now(), updated_at = now() WHERE id = :i AND farm_id = :f"), {"i": crop_id, "f": farm_id})


# ---------- seasons ----------

async def get_season(session: AsyncSession, farm_id: uuid.UUID, field_id: uuid.UUID, season_id: uuid.UUID) -> dict[str, Any]:
    row = await _one(
        session,
        f"SELECT {SEASON_COLS} FROM seasons WHERE id = :i AND farm_id = :f AND field_id = :fi",
        i=season_id, f=farm_id, fi=field_id,
    )
    if row is None:
        raise FieldError(404, "not_found")
    return row


def _variety(data: Data) -> dict[str, Any]:
    if "variety" not in data:
        return {}
    value = data["variety"]
    if value is not None and not (isinstance(value, str) and len(value) <= 80):
        raise _bad("variety")
    return {"variety": value}


async def create_season(
    session: AsyncSession, farm_id: uuid.UUID, field_id: uuid.UUID, data: Data, season_id: uuid.UUID | None = None
) -> dict[str, Any]:
    crop = await get_crop(session, farm_id, data.get("crop_id"))  # 404 for a crop of another farm
    started = _date(data, "started_at", required=True)
    sowing = _date(data, "sowing_date")
    planting = data.get("planting_year")
    if planting is not None and (isinstance(planting, bool) or not isinstance(planting, int)):
        raise _bad("planting_year")
    assert started is not None
    bad = season_dates_error(crop["cycle"], planting, sowing, started, None)
    if bad:
        raise _bad(bad)
    season_id = season_id or uuid.uuid4()
    estimated = estimate_stage(crop, {"sowing_date": sowing.isoformat() if sowing else None}, dt.date.today().isoformat())["stage"]
    close_ids = data.get("close_ids") or []
    if close_ids:
        try:
            ids = [uuid.UUID(str(c)) for c in close_ids]
        except ValueError:
            raise _bad("close_ids") from None
        await session.execute(
            text("UPDATE seasons SET ended_at = GREATEST(:d, started_at), updated_at = now() WHERE farm_id = :f AND field_id = :fi AND ended_at IS NULL AND id = ANY(:ids)"),
            {"d": started, "f": farm_id, "fi": field_id, "ids": ids},
        )
    active = await _one(
        session, "SELECT 1 AS x FROM seasons WHERE farm_id = :f AND field_id = :fi AND crop_id = :c AND ended_at IS NULL",
        f=farm_id, fi=field_id, c=crop["id"],
    )
    if active:
        raise FieldError(409, "season_already_active")
    try:
        async with session.begin_nested():
            await session.execute(
                text(
                    "INSERT INTO seasons (id, farm_id, field_id, crop_id, variety, planting_year, sowing_date, started_at, destination, stage_estimated)"
                    " VALUES (:id, :f, :fi, :c, :variety, :py, :sd, :st, :dest, :est)"
                ),
                {"id": season_id, "f": farm_id, "fi": field_id, "c": crop["id"], "variety": _variety(data).get("variety"),
                 "py": planting, "sd": sowing, "st": started, "dest": data.get("destination"), "est": estimated},
            )
    except IntegrityError:
        raise FieldError(409, "season_already_active") from None
    return await get_season(session, farm_id, field_id, season_id)


async def update_season(session: AsyncSession, farm_id: uuid.UUID, field_id: uuid.UUID, season_id: uuid.UUID, data: Data) -> dict[str, Any]:
    current = await get_season(session, farm_id, field_id, season_id)
    values: dict[str, Any] = _variety(data)
    if "destination" in data:
        values["destination"] = data["destination"] if isinstance(data["destination"], str | type(None)) else None
    if "stage_corrected" in data:
        if data["stage_corrected"] is not None and not (isinstance(data["stage_corrected"], str) and len(data["stage_corrected"]) <= 40):
            raise _bad("stage_corrected")
        values["stage_corrected"] = data["stage_corrected"]
    if "ended_at" in data:
        ended = _date(data, "ended_at")
        if ended is not None and ended < current["started_at"]:
            raise _bad("ended_at")
        values["ended_at"] = ended
    sets = [f"{k} = :{k}" for k in values]
    if "stage_corrected" in values:
        sets.append("stage_corrected_at = now()")
    if sets:
        try:
            async with session.begin_nested():
                await session.execute(
                    text(f"UPDATE seasons SET {', '.join(sets)}, server_version = server_version + 1, updated_at = now() WHERE id = :i AND farm_id = :f"),
                    {"i": season_id, "f": farm_id, **values},
                )
        except IntegrityError:
            raise FieldError(409, "season_already_active") from None
    return await get_season(session, farm_id, field_id, season_id)
