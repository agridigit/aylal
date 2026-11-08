"""Shared F4 fixtures/helpers for integration tests (real PostgreSQL, no mocks).

Rows are seeded with plain SQL against the columns of specs/007-irrigation-water-balance/data-model.md: before the
migration exists the failure is UndefinedTable, which is the right reason. Time is NEVER read from the system: the
fixture `clock4` overrides the `get_clock` dependency with a FixedClock (local day 2026-06-04, 02:00 in Casablanca).
"""
import asyncio
import datetime as dt
import json
import uuid

import pytest

from tests.helpers import auth, sql
from tests.integration._f2 import add_field, assign, new_user  # noqa: F401  (re-exported)

NOW4 = dt.datetime(2026, 6, 4, 1, 0, tzinfo=dt.UTC)
TODAY4 = dt.date(2026, 6, 4)
YESTERDAY4 = dt.date(2026, 6, 3)
NOT_FOUND = {"detail": "not_found"}
FORBIDDEN = {"detail": "forbidden"}
WORKER_FORBIDDEN_KEY_PARTS = ("ece", "ecw", "salin", "water_source", "analysis_age", "soil", "taw", "raw", "moisture", "leaching", "cost")
WORKER_ASSUMPTION_KEYS = {"et0", "kc", "effective_rain", "efficiency", "application_rate", "rain_source"}
ASSUMPTIONS_FULL = [
    {"key": "et0", "value": 5.1, "source": "gateway"}, {"key": "kc", "value": 0.7, "source": "referential"},
    {"key": "efficiency", "value": 0.9, "source": "default"}, {"key": "rain_source", "value": "forecast", "source": "gateway"},
    {"key": "ece_ds_m", "value": 3.2, "source": "user"}, {"key": "water_source", "value": "well-42", "source": "user"},
    {"key": "analysis_age_days", "value": 400, "source": "computed"}, {"key": "soil_texture", "value": "clay-fixture", "source": "referential"},
    {"key": "taw_mm", "value": 61, "source": "computed"}, {"key": "x_future", "value": 1, "source": "computed"},
]
ASSUMPTIONS_WORKER = [a for a in ASSUMPTIONS_FULL if a["key"] in WORKER_ASSUMPTION_KEYS]


@pytest.fixture
def clock4():
    yield from _fixed_clock()


def _fixed_clock():
    from app.domain.clock import FixedClock, get_clock
    from app.main import app

    clock = FixedClock(NOW4)
    app.dependency_overrides[get_clock] = lambda: clock
    yield clock
    app.dependency_overrides.pop(get_clock, None)


def seed_system(farm, parcel, kind="drip", sectors=2):
    sid = uuid.uuid4()
    sql("INSERT INTO irrigation_systems (id, farm_id, parcel_id, kind, emitter_flow_lph, emitter_spacing_m, row_spacing_m, sectors_count)"
        " VALUES ($1,$2,$3,$4,4,0.5,2,$5)", sid, farm, parcel, kind, sectors)
    return sid


def seed_season(farm, parcel):
    cid, slug, sid = uuid.uuid4(), f"fx_{uuid.uuid4().hex[:10]}", uuid.uuid4()
    sql("INSERT INTO crops (id, slug, name_ary, name_ar, name_fr, cycle) VALUES ($1,$2,$2,$2,$2,'perennial')", cid, slug)
    sql("INSERT INTO seasons (id, farm_id, field_id, crop_id, started_at) VALUES ($1,$2,$3,$4,$5)", sid, farm, parcel, cid, dt.date(2026, 3, 1))
    return sid


def seed_event(farm, parcel, author, *, volume=12.0, net_mm=2.0, day=YESTERDAY4, status="done", season=None, note="fixture note"):
    from app.irrigation.ids import operation_id_for

    eid = uuid.uuid4()
    oid = operation_id_for(farm, eid)
    sql("INSERT INTO operations (id, farm_id, type, performed_on, status, author_id, season_id) VALUES ($1,$2,'irrigation',$3,'done',$4,$5)", oid, farm, day, author, season)
    sql("INSERT INTO irrigation_events (id, farm_id, parcel_id, season_id, operation_id, performed_on, sector_no, input_mode, duration_min, volume_m3, net_mm, author_id, note, status)"
        " VALUES ($1,$2,$3,$4,$5,$6,NULL,'duration',60,$7,$8,$9,$10,$11)", eid, farm, parcel, season, oid, day, volume, net_mm, author, note, status)
    return eid


def seed_plan(farm, parcel, *, kind="irrigate", day=TODAY4, minutes=120, leaching=0.08, reason=None, stress=None):
    pid = uuid.uuid4()
    sql("INSERT INTO irrigation_plans (id, farm_id, parcel_id, for_date, kind, total_minutes, sectors, net_need_mm, leaching_fraction, stress_level, confidence,"
        " assumptions, worker_assumptions, unavailable_reason, computed_at, ready_before_7)"
        " VALUES ($1,$2,$3,$4,$5,$6,$7::jsonb,12.5,$8,$9,'medium',$10::jsonb,$11::jsonb,$12,$13,true)",
        pid, farm, parcel, day, kind, None if kind != "irrigate" else minutes, json.dumps([{"sector_no": 1, "minutes": minutes, "volume_m3": 6.0}]),
        leaching, stress, json.dumps(ASSUMPTIONS_FULL), json.dumps(ASSUMPTIONS_WORKER), reason, NOW4)
    return pid


def seed_balance(farm, parcel, day=YESTERDAY4):
    sql("INSERT INTO water_balance_days (id, farm_id, parcel_id, day, et0_mm, et0_method, kc, etc_mm, rain_mm, rain_source, rain_eff_mm, irrigation_net_mm, taw_mm, raw_mm, depletion_mm, moisture_source)"
        " VALUES (gen_random_uuid(),$1,$2,$3,5,'hargreaves',0.7,3.5,0,'forecast',0,0,61,30,12,'sensor:fixture')", farm, parcel, day)


def seed_analysis(farm, parcel, author, ec=3.1):
    aid = uuid.uuid4()
    sql("INSERT INTO water_analyses (id, farm_id, parcel_id, water_source, ec_ds_m, analysed_on, author_id) VALUES ($1,$2,$3,'well-42',$4,$5,$6)", aid, farm, parcel, ec, dt.date(2026, 5, 1), author)
    return aid


def seed_f4_rows(farm, parcel, author):
    """One event, one analysis and one balance day for a parcel (world4 already seeds a system and a plan per parcel); returns ids."""
    seed_balance(farm, parcel)
    return dict(event=seed_event(farm, parcel, author), analysis=seed_analysis(farm, parcel, author))


@pytest.fixture
def world4(make_farm):
    """(Installs the injected clock for the whole test.) Farm A with 10 irrigated parcels (system + plan each), 3 assigned to the worker (p0..p2); p5 is invisible to the worker."""
    clock = _fixed_clock()
    next(clock)
    try:
        yield _build_world(make_farm)
    finally:
        next(clock, None)


def _build_world(make_farm):
    owner, manager, worker, worker2, owner_b, outsider = (new_user() for _ in range(6))
    farm_a = make_farm({owner: "owner", manager: "manager", worker: "worker", worker2: "worker"})
    farm_b = make_farm({owner_b: "owner"})
    p = [add_field(farm_a, f"P{i}", lon=-7.60 + i * 0.01) for i in range(10)]
    b1 = add_field(farm_b, "B1", lon=-7.5)
    for i in range(3):
        assign(farm_a, worker, p[i])
    sql("UPDATE parcels SET irrigation='drip' WHERE id = ANY($1)", p + [b1])
    for i, parcel in enumerate(p):
        seed_system(farm_a, parcel)
        seed_plan(farm_a, parcel, minutes=100 + i)
    seed_system(farm_b, b1)
    seed_plan(farm_b, b1)
    return dict(owner=owner, manager=manager, worker=worker, worker2=worker2, owner_b=owner_b, outsider=outsider,
                farm_a=farm_a, farm_b=farm_b, p=p, b1=b1, a1=p[0], hidden=p[5])


SYSTEM_BODY = {"kind": "drip", "sectors_count": 2, "pump_flow_m3h": 10}


def routes(farm, parcel, event):
    """Every F4 farm route as (name, method, path, json body) addressed on `farm`."""
    f = f"/v1/farms/{farm}"
    pa = f"{f}/parcels/{parcel}"
    return [
        ("getIrrigationSystem", "GET", f"{pa}/irrigation-system", None),
        ("putIrrigationSystem", "PUT", f"{pa}/irrigation-system", SYSTEM_BODY),
        ("listSystemVersions", "GET", f"{pa}/irrigation-system/versions", None),
        ("listAdvice", "GET", f"{f}/irrigation/advice", None),
        ("getAdvice", "GET", f"{pa}/irrigation/advice", None),
        ("getBalance", "GET", f"{pa}/irrigation/balance", None),
        ("listEvents", "GET", f"{pa}/irrigation/events", None),
        ("recordIrrigation", "POST", f"{pa}/irrigation/events", {"id": str(uuid.uuid4()), "performed_on": "2026-06-03", "duration_min": 30}),
        ("cancelIrrigation", "POST", f"{pa}/irrigation/events/{event}/cancel", None),
        ("getConsumption", "GET", f"{f}/irrigation/consumption", None),
        ("listWaterAnalyses", "GET", f"{pa}/water-analyses", None),
        ("addWaterAnalysis", "POST", f"{pa}/water-analyses", {"id": str(uuid.uuid4()), "ec_ds_m": 2.1, "analysed_on": "2026-06-01"}),
    ]


def call(client, token, method, path, body=None):
    return client.request(method, path, headers=auth(token), json=body)


def sync_op(table, farm, rid, fields, kind="put", op_id=None):
    return {"op_id": str(op_id or uuid.uuid4()), "table": table, "kind": kind, "record_id": str(rid), "farm_id": str(farm), "base_version": 0, "fields": fields}


def sync_event(farm, parcel, rid=None, **extra):
    """A /v1/sync/upload op creating an irrigation event (the client never sends server fields)."""
    return sync_op("irrigation_events", farm, rid or uuid.uuid4(), {"parcel_id": str(parcel), "performed_on": "2026-06-03", "duration_min": 30, **extra})


def sync_post(client, token, ops):
    return client.post("/v1/sync/upload", json={"ops": ops}, headers=auth(token))


def keys_of(obj):
    """All dict keys, recursively."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            if k == "key" and isinstance(v, str):
                yield v  # assumptions are {key, value, source}: the assumption NAME is a key too
            yield from keys_of(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from keys_of(v)


def assert_worker_safe(obj, where=""):
    bad = [k for k in keys_of(obj) if any(k.lower().startswith(p) for p in WORKER_FORBIDDEN_KEY_PARTS)]
    assert not bad, f"{where}: forbidden keys for the worker: {sorted(set(bad))}"


def export_of(user):
    from app.accounts.export import build_export
    from app.db.session import sessionmaker

    async def run():
        async with sessionmaker() as s:
            return await build_export(s, user)

    return asyncio.run(run())


def flush_f4_redis():
    """Delete the F4 keys only (limiter, caches, versions). Never FLUSHDB: other tests of the same worker share Redis."""
    import redis

    from app.config import get_settings

    client = redis.from_url(get_settings().redis_url)
    try:
        for pattern in ("f4:*", "irr:*", "irrver:*", "gw:*"):
            for key in client.scan_iter(pattern):
                client.delete(key)
    finally:
        client.close()


def seed_referentials(farm, parcel, *, with_crop=True):
    """FIXTURE referential rows for one parcel (the migration seeds nothing). Values are arbitrary test inputs, not agronomy.
    Returns (crop_slug, stage_key). With `with_crop=False` the season exists but the crop has no row in crop_irrigation_params."""
    cid, slug, stage = uuid.uuid4(), f"fx_{uuid.uuid4().hex[:10]}", "fixture_stage"
    sql("INSERT INTO crops (id, slug, name_ary, name_ar, name_fr, cycle) VALUES ($1,$2,$2,$2,$2,'perennial')", cid, slug)
    sql("INSERT INTO seasons (id, farm_id, field_id, crop_id, started_at, stage_corrected) VALUES ($1,$2,$3,$4,$5,$6)", uuid.uuid4(), farm, parcel, cid, dt.date(2026, 3, 1), stage)
    sql("UPDATE parcels SET soil='fixture_soil', irrigation='drip' WHERE id=$1", parcel)
    sql("UPDATE farms SET location=ST_SetSRID(ST_MakePoint(-7.6, 33.6), 4326) WHERE id=$1", farm)
    if with_crop:
        sql("INSERT INTO crop_irrigation_params (crop_slug, stage_key, kc, root_depth_m, depletion_fraction, ece_threshold_ds_m, ece_max_ds_m, validated, validated_by, source, imported_at)"
            " VALUES ($1,$2,0.7,0.5,0.5,2,8,true,'fixture','fixture',now())", slug, stage)
    sql("INSERT INTO soil_textures (texture_key, available_water_mm_per_m, validated_by, source) VALUES ('fixture_soil', 100, 'fixture', 'fixture') ON CONFLICT (texture_key) DO NOTHING")
    for key, value in (("effective_rain", {"method": "fraction", "params": {"fraction": 0.5}}), ("leaching_max", 0.15), ("stress_watch_ratio", 0.5)):
        sql("INSERT INTO irrigation_params (key, value, validated_by, source) VALUES ($1,$2::jsonb,'fixture','fixture') ON CONFLICT (key) DO NOTHING", key, json.dumps(value))
    return slug, stage


def seed_weather_days(farm, days=3, rain=0.0, age_h=1):
    """A fresh forecast starting on the injected local day, without et0_mm (so ET0 is computed by Hargreaves)."""
    rows = [{"date": (TODAY4 + dt.timedelta(days=i)).isoformat(), "tmin": 14.0, "tmax": 29.0, "rain_mm": rain, "wind_kmh": 8.0, "humidity_pct": 50.0, "code": 1} for i in range(days)]
    sql("INSERT INTO farm_weather (farm_id, cell_id, fetched_at, availability, days) VALUES ($1,'33.6:-7.6',$2,'ok',$3::jsonb)"
        " ON CONFLICT (farm_id) DO UPDATE SET fetched_at=EXCLUDED.fetched_at, availability='ok', days=EXCLUDED.days", farm, NOW4 - dt.timedelta(hours=age_h), json.dumps(rows))


def compute(farm, parcel):
    """Run the plan computation of one parcel at the injected instant (the same function the worker calls)."""
    from app.db.session import sessionmaker
    from app.domain.clock import FixedClock
    from app.irrigation.plans import compute_parcel_plan

    async def go():
        async with sessionmaker() as s:
            out = await compute_parcel_plan(s, farm, parcel, FixedClock(NOW4))
            await s.commit()
            return out

    return asyncio.run(go())
