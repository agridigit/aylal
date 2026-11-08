"""Shared seeds of the F4 worker story tests (real PostgreSQL, asyncpg). Fixture referentials are arbitrary test inputs, not agronomy.
Time is always an injected ISO instant (`now=`), never the system clock."""
import datetime as dt
import json
import uuid

from tests._f3 import seed_crop, seed_farm, seed_parcel

NOW = "2026-06-04T01:00:00+00:00"      # 02:00 in Casablanca, local day 2026-06-04
AT_03 = "2026-06-04T02:00:00+00:00"    # 03:00 local
AT_09 = "2026-06-04T08:00:00+00:00"    # 09:00 local
FETCHED = dt.datetime(2026, 6, 4, 0, 30, tzinfo=dt.UTC)
DAY = dt.date(2026, 6, 4)


async def seed_world(conn, *, rain=0.0, depletion=40.0, with_system=True):
    """A farm with a location, a forecast of `rain` mm per day, fixture referentials and one irrigated drip parcel (4 mm/h, 2 sectors)
    whose last stored balance day already shows `depletion` mm. Returns (farm, parcel)."""
    farm = await seed_farm(conn, lat=33.6, lon=-7.6)
    parcel = await seed_parcel(conn, farm, area=1.0)
    await conn.execute("UPDATE parcels SET irrigation='drip', soil='fixture_soil' WHERE id=$1", parcel)
    cid, slug = await seed_crop(conn)
    await conn.execute("INSERT INTO seasons (id, farm_id, field_id, crop_id, started_at, stage_corrected) VALUES ($1,$2,$3,$4,$5,'fixture_stage')", uuid.uuid4(), farm, parcel, cid, dt.date(2026, 3, 1))
    await conn.execute("INSERT INTO crop_irrigation_params (crop_slug, stage_key, kc, root_depth_m, depletion_fraction, ece_threshold_ds_m, ece_max_ds_m, validated, validated_by, source, imported_at)"
                       " VALUES ($1,'fixture_stage',0.7,0.5,0.5,2,8,true,'fixture','fixture',now())", slug)
    await conn.execute("INSERT INTO soil_textures (texture_key, available_water_mm_per_m, validated_by, source) VALUES ('fixture_soil',100,'fixture','fixture') ON CONFLICT (texture_key) DO NOTHING")
    for key, value in (("effective_rain", {"method": "fraction", "params": {"fraction": 0.5}}), ("leaching_max", 0.15), ("stress_watch_ratio", 0.5)):
        await conn.execute("INSERT INTO irrigation_params (key, value, validated_by, source) VALUES ($1,$2::jsonb,'fixture','fixture') ON CONFLICT (key) DO NOTHING", key, json.dumps(value))
    days = [{"date": (DAY + dt.timedelta(days=i)).isoformat(), "tmin": 14.0, "tmax": 29.0, "rain_mm": rain, "wind_kmh": 8.0, "humidity_pct": 50.0, "code": 1} for i in range(8)]
    await conn.execute("INSERT INTO farm_weather (farm_id, cell_id, fetched_at, availability, days) VALUES ($1,'33.6:-7.6',$2,'ok',$3::jsonb)", farm, FETCHED, json.dumps(days))
    if with_system:
        await conn.execute("INSERT INTO irrigation_systems (id, farm_id, parcel_id, kind, emitter_flow_lph, emitter_spacing_m, row_spacing_m, sectors_count)"
                           " VALUES ($1,$2,$3,'drip',4,0.5,2,2)", uuid.uuid4(), farm, parcel)
    await conn.execute("INSERT INTO water_balance_days (id, farm_id, parcel_id, day, et0_mm, et0_method, kc, etc_mm, rain_mm, rain_source, rain_eff_mm, irrigation_net_mm, taw_mm, raw_mm, depletion_mm)"
                       " VALUES (gen_random_uuid(),$1,$2,$3,5,'hargreaves',0.7,3.5,0,'forecast',0,0,50,25,$4)", farm, parcel, DAY - dt.timedelta(days=2), depletion)
    return farm, parcel


async def plan(conn, parcel, day=DAY):
    return await conn.fetchrow("SELECT kind, total_minutes, ready_before_7, computed_at FROM irrigation_plans WHERE parcel_id=$1 AND for_date=$2", parcel, day)


async def add_member(conn, farm, role, *, removed=False, token=None):
    user = uuid.uuid4()
    await conn.execute("INSERT INTO users (id, phone_e164, status, language) VALUES ($1,$2,'active','fr')", user, f"+2126{uuid.uuid4().int % 10**8:08d}")
    await conn.execute("INSERT INTO farm_members (farm_id, user_id, role, removed_at) VALUES ($1,$2,$3,$4)", farm, user, role, dt.datetime.now(dt.UTC) if removed else None)
    if token:
        await conn.execute("INSERT INTO notification_prefs (farm_id, user_id, summary_hour, alerts_enabled, push_token) VALUES ($1,$2,7,true,$3)", farm, user, token)
    return user


class SpyRedis:
    """arq-like pool: records enqueue_job calls."""

    def __init__(self):
        self.jobs = []

    async def enqueue_job(self, name, *args, **kwargs):
        self.jobs.append((name, kwargs))


class SpyPush:
    def __init__(self):
        self.sent = []

    def configured(self):
        return True

    def send(self, **kwargs):
        self.sent.append(kwargs)
        return {"availability": "ok"}
