"""Shared builders of the F4 story tests (US2..US5): a parcel with a system, fixture referentials and a forecast, computed at the
injected instant. Fixture values are arbitrary test inputs, not agronomy. Time comes from `_f4` (never the system clock)."""
import datetime as dt
import uuid

from tests.helpers import sql
from tests.integration._f2 import add_field
from tests.integration._f4 import (  # noqa: F401
    TODAY4,
    YESTERDAY4,
    compute,
    seed_referentials,
    seed_system,
    seed_weather_days,
)


def depleted_parcel(w, name="Dep", *, depletion=40.0, rain=0.0, sectors=2, lon=-7.20, with_system=True):
    """A new irrigated drip parcel (4 L/h, 0.5 m x 2 m = 4 mm/h) whose last stored balance day (the day before yesterday: the engine replays from yesterday) already shows `depletion` mm
    of depletion (above RAW with the fixture referentials), a fresh forecast of `rain` mm per day and NO computed plan yet."""
    farm = w["farm_a"]
    parcel = add_field(farm, name, lon=lon)
    sql("UPDATE parcels SET irrigation='drip' WHERE id=$1", parcel)
    seed_referentials(farm, parcel)
    if with_system:
        seed_system(farm, parcel, sectors=sectors)
    seed_weather_days(farm, rain=rain)
    seed_depletion(farm, parcel, depletion)
    return parcel


def seed_depletion(farm, parcel, depletion, day=YESTERDAY4 - dt.timedelta(days=1)):
    sql("INSERT INTO water_balance_days (id, farm_id, parcel_id, day, et0_mm, et0_method, kc, etc_mm, rain_mm, rain_source, rain_eff_mm, irrigation_net_mm, taw_mm, raw_mm, depletion_mm)"
        " VALUES (gen_random_uuid(),$1,$2,$3,5,'hargreaves',0.7,3.5,0,'forecast',0,0,50,25,$4)", farm, parcel, day, depletion)


def plan_of(parcel, day=TODAY4):
    rows = sql("SELECT kind, total_minutes, net_need_mm, unavailable_reason, confidence, assumptions, sectors, ready_before_7, leaching_fraction FROM irrigation_plans"
               " WHERE parcel_id=$1 AND for_date=$2", parcel, day)
    return rows[0] if rows else None


def assumption(advice, key):
    return next((a for a in advice["assumptions"] if a["key"] == key), None)


def advice_url(w, parcel):
    return f"/v1/farms/{w['farm_a']}/parcels/{parcel}/irrigation/advice"


def seed_analysis_on(farm, parcel, author, ec, day=dt.date(2026, 5, 20), source="well-42"):
    aid = uuid.uuid4()
    sql("INSERT INTO water_analyses (id, farm_id, parcel_id, water_source, ec_ds_m, analysed_on, author_id) VALUES ($1,$2,$3,$4,$5,$6,$7)", aid, farm, parcel, source, ec, day, author)
    return aid
