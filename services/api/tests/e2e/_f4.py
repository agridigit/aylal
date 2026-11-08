"""Shared helpers of the F4 e2e tests (running stack). Phone numbers are unique per call; nothing here deletes a row; time is a fixed
instant handed to the worker jobs (`now=`), never read from the system."""
import datetime as dt
import json
import uuid

import httpx

from tests.e2e._f2 import BASE, CASA, square, unique_phone  # noqa: F401  (unique_phone re-exported: the single phone generator)
from tests.e2e._f3 import client, headers, login, run_job  # noqa: F401
from tests.helpers import sql

NOW = "2026-06-04T01:00:00+00:00"          # 02:00 in Casablanca: before 7 h, local day 2026-06-04
DAY = dt.date(2026, 6, 4)


def farm_with_worker(c: httpx.Client, parcels: int = 10, assigned: int = 3):
    """A new farm (unique owner and worker phones), `parcels` irrigated drip parcels, the worker assigned to the first `assigned`."""
    owner = login(c, unique_phone())
    oh = headers(owner)
    farm = c.post("/farms", json={"name": "Atlas", "location": CASA}, headers=oh).json()["id"]
    ids = [c.post(f"/farms/{farm}/fields", json={"name": f"P{i}", "geometry": square(-7.60 + i * 0.01), "irrigation": "drip"}, headers=oh).json()["id"] for i in range(parcels)]
    phone = unique_phone()
    assert c.post(f"/farms/{farm}/invitations", json={"phone": phone, "role": "worker"}, headers=oh).status_code == 201
    worker = login(c, phone)
    wid = worker["user"]["id"]
    assert c.put(f"/farms/{farm}/members/{wid}/parcels", json={"parcel_ids": ids[:assigned]}, headers=oh).status_code == 200
    return dict(farm=farm, oh=oh, wh=headers(worker), worker_id=wid, owner_id=owner["user"]["id"], parcels=ids, mine=ids[:assigned], hidden=ids[-1])


def seed_forecast(farm: str, rain_mm: float = 0.0) -> None:
    rows = [{"date": (DAY + dt.timedelta(days=i)).isoformat(), "tmin": 14.0, "tmax": 29.0, "rain_mm": rain_mm, "wind_kmh": 8.0, "humidity_pct": 50.0, "code": 1} for i in range(8)]
    sql("INSERT INTO farm_weather (farm_id, cell_id, fetched_at, availability, days) VALUES ($1,'33.6:-7.6',$2,'ok',$3::jsonb)"
        " ON CONFLICT (farm_id) DO UPDATE SET fetched_at=EXCLUDED.fetched_at, availability='ok', days=EXCLUDED.days",
        uuid.UUID(farm), dt.datetime(2026, 6, 4, 0, 30, tzinfo=dt.UTC), json.dumps(rows))


def seed_crop_without_irrigation_params(farm: str, parcel: str) -> str:
    """An active season of a unique crop that has NO row in crop_irrigation_params (the referentials are empty by default)."""
    cid, slug = uuid.uuid4(), f"fx_{uuid.uuid4().hex[:10]}"
    sql("INSERT INTO crops (id, slug, name_ary, name_ar, name_fr, cycle) VALUES ($1,$2,$2,$2,$2,'perennial')", cid, slug)
    sql("INSERT INTO seasons (id, farm_id, field_id, crop_id, started_at, stage_corrected) VALUES ($1,$2,$3,$4,$5,'fixture_stage')", uuid.uuid4(), uuid.UUID(farm), uuid.UUID(parcel), cid, dt.date(2026, 3, 1))
    return slug


def seed_event(farm: str, parcel: str, author: str, volume: float) -> None:
    from app.irrigation.ids import operation_id_for

    eid = uuid.uuid4()
    oid = operation_id_for(uuid.UUID(farm), eid)
    sql("INSERT INTO operations (id, farm_id, type, performed_on, status, author_id) VALUES ($1,$2,'irrigation',$3,'done',$4)", oid, uuid.UUID(farm), dt.date(2026, 6, 3), uuid.UUID(author))
    sql("INSERT INTO irrigation_events (id, farm_id, parcel_id, operation_id, performed_on, input_mode, duration_min, volume_m3, net_mm, author_id, status)"
        " VALUES ($1,$2,$3,$4,$5,'duration',60,$6,2.0,$7,'done')", eid, uuid.UUID(farm), uuid.UUID(parcel), oid, dt.date(2026, 6, 3), volume, uuid.UUID(author))
