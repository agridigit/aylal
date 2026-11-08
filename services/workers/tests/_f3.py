"""Shared F3 seeds for worker tests (real PostgreSQL). Rows are unique per call and never deleted (protected tables stay intact)."""
import asyncio
import datetime as dt
import json
import os
import uuid

import asyncpg
import pytest

DSN = os.environ.get("AYLAL_DATABASE_URL", "postgresql://aylal:aylal_dev@db:5432/aylal")
TODAY = dt.datetime.now(dt.UTC).date()
SQUARE = json.dumps({"type": "Polygon", "coordinates": [[[-7.60, 33.57], [-7.598, 33.57], [-7.598, 33.572], [-7.60, 33.572], [-7.60, 33.57]]]})


def run(fn):
    async def _go():
        try:
            conn = await asyncpg.connect(DSN, timeout=5)
        except (OSError, asyncpg.PostgresError) as e:  # the compose database must be up
            pytest.skip(f"database unreachable: {e}")
        try:
            return await fn(conn)
        finally:
            await conn.close()

    return asyncio.run(_go())


async def seed_farm(conn, *, lat=None, lon=None):
    farm = uuid.uuid4()
    if lat is None:
        await conn.execute("INSERT INTO farms (id, name) VALUES ($1, 'F3 fixture')", farm)
    else:
        await conn.execute("INSERT INTO farms (id, name, location) VALUES ($1, 'F3 fixture', ST_SetSRID(ST_MakePoint($3, $2), 4326))", farm, lat, lon)
    return farm


async def seed_parcel(conn, farm, *, greenhouse=False, area=1.0, archived=False):
    pid = uuid.uuid4()
    await conn.execute(
        "INSERT INTO parcels (id, farm_id, name, geometry, area_declared_ha, greenhouse, archived_at)"
        " VALUES ($1,$2,$3,ST_SetSRID(ST_GeomFromGeoJSON($4),4326),$5,$6,$7)",
        pid, farm, f"P-{pid.hex[:6]}", SQUARE, area, greenhouse, dt.datetime.now(dt.UTC) if archived else None,
    )
    return pid


async def seed_crop(conn):
    """A reference crop with a unique slug, so its fixture thresholds never collide with another test."""
    cid, slug = uuid.uuid4(), f"fx_{uuid.uuid4().hex[:10]}"
    await conn.execute("INSERT INTO crops (id, slug, name_ary, name_ar, name_fr, cycle) VALUES ($1,$2,$2,$2,$2,'perennial')", cid, slug)
    return cid, slug


async def seed_threshold(conn, slug, stage="fixture_flowering", frost_c=-2):
    await conn.execute(
        "INSERT INTO crop_weather_thresholds (crop_slug, stage_key, frost_c, chergui_tmax_c, chergui_rh_max_pct, chergui_wind_kmh,"
        " heavy_rain_mm_24h, strong_wind_kmh, source) VALUES ($1,$2,$3,38,30,25,40,30,'fixture')", slug, stage, frost_c)


async def seed_season(conn, farm, parcel, crop_id, stage="fixture_flowering"):
    sid = uuid.uuid4()
    await conn.execute("INSERT INTO seasons (id, farm_id, field_id, crop_id, started_at, stage_corrected) VALUES ($1,$2,$3,$4,$5,$6)",
                       sid, farm, parcel, crop_id, TODAY - dt.timedelta(days=100), stage)
    return sid


def day(offset, **over):
    d = {"date": (TODAY + dt.timedelta(days=offset)).isoformat(), "tmin": 8.0, "tmax": 22.0, "rain_mm": 0.0, "wind_kmh": 8.0, "humidity_pct": 60.0, "icon": "sun"}
    return {**d, **over}


async def seed_weather(conn, farm, days):
    await conn.execute(
        "INSERT INTO farm_weather (farm_id, cell_id, fetched_at, availability, days) VALUES ($1,'29.0:-9.0',now(),'ok',$2::jsonb)"
        " ON CONFLICT (farm_id) DO UPDATE SET days = EXCLUDED.days, fetched_at = now(), availability = 'ok'", farm, json.dumps(days))


async def alerts_of(conn, farm):
    return [dict(r) for r in await conn.fetch("SELECT * FROM alerts WHERE farm_id = $1 ORDER BY forecast_day, type", farm)]
