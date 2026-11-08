"""Shared helpers of the F3 story e2e tests: unique phones, login through the proxy, farm setup, and worker jobs run on the real worker.

Nothing here deletes a row: every run uses new phone numbers, farms and crops.
"""
import asyncio
import datetime as dt
import json
import os
import uuid
from urllib.parse import urlparse

import httpx
from arq import create_pool
from arq.connections import RedisSettings

from tests.e2e._f2 import BASE, CASA, square, unique_phone
from tests.helpers import sql

TODAY = dt.date.today()


def login(c: httpx.Client, phone: str) -> dict:
    assert c.post("/auth/otp/request", json={"phone": phone}).status_code == 202
    r = c.post("/auth/otp/verify", json={"phone": phone, "code": "000000"})
    assert r.status_code == 200, r.text
    return r.json()


def client() -> httpx.Client:
    return httpx.Client(base_url=BASE, verify=False, timeout=60)


def headers(session: dict) -> dict:
    return {"Authorization": f"Bearer {session['access_token']}"}


_OWNER: dict = {}  # one OTP login per run: the request limiter is per client IP, so tests share the owner and create their own farms


def setup_farm(c: httpx.Client, parcels: int = 3, *, worker: bool = False, hidden: int = 0, lon0: float = -7.60):
    """The shared owner (+ optional new worker assigned to all parcels but the last `hidden` ones) on a new located farm with `parcels` parcels."""
    if not _OWNER:
        _OWNER.update(login(c, unique_phone()))
    owner = _OWNER
    oh = headers(owner)
    farm = c.post("/farms", json={"name": "Atlas", "location": CASA}, headers=oh).json()["id"]
    ids = [c.post(f"/farms/{farm}/fields", json={"name": f"P{i}", "geometry": square(lon0 + i * 0.01)}, headers=oh).json()["id"] for i in range(parcels)]
    out = {"farm": farm, "oh": oh, "owner": owner, "parcels": ids, "worker": None, "wh": None}
    if worker:
        phone = unique_phone()
        assert c.post(f"/farms/{farm}/invitations", json={"phone": phone, "role": "worker"}, headers=oh).status_code == 201
        w = login(c, phone)
        assert c.put(f"/farms/{farm}/members/{w['user']['id']}/parcels", json={"parcel_ids": ids[: len(ids) - hidden]}, headers=oh).status_code == 200
        out.update(worker=w, wh=headers(w))
    return out


def run_job(name: str, **kwargs):
    """Enqueue a job on the real worker and wait for its result."""
    async def _go():
        u = urlparse(os.environ.get("AYLAL_REDIS_URL", "redis://redis:6379/0"))
        pool = await create_pool(RedisSettings(host=u.hostname or "redis", port=u.port or 6379))
        job = await pool.enqueue_job(name, **kwargs)
        assert job is not None, f"job {name} was not enqueued"
        return await job.result(timeout=90)

    return asyncio.run(_go())


def seed_crop_stage(farm: str, parcel: str, *, frost_c: float | None, stage: str = "fixture_flowering") -> str:
    """A unique reference crop with a FIXTURE threshold and an active season at `stage`; returns the crop slug."""
    cid, slug = uuid.uuid4(), f"fx_{uuid.uuid4().hex[:10]}"
    sql("INSERT INTO crops (id, slug, name_ary, name_ar, name_fr, cycle) VALUES ($1,$2,$2,$2,$2,'perennial')", cid, slug)
    sql("INSERT INTO crop_weather_thresholds (crop_slug, stage_key, frost_c, chergui_tmax_c, chergui_rh_max_pct, chergui_wind_kmh, heavy_rain_mm_24h, strong_wind_kmh, source)"
        " VALUES ($1,$2,$3,38,30,25,40,30,'fixture')", slug, stage, frost_c)
    sql("INSERT INTO seasons (id, farm_id, field_id, crop_id, started_at, stage_corrected) VALUES ($1,$2,$3,$4,$5,$6)",
        uuid.uuid4(), uuid.UUID(farm), uuid.UUID(parcel), cid, TODAY - dt.timedelta(days=90), stage)
    return slug


def seed_forecast(farm: str, days: list[dict], age_h: int = 1) -> None:
    sql("INSERT INTO farm_weather (farm_id, cell_id, fetched_at, availability, days) VALUES ($1,'33.6:-7.6',now() - $2 * interval '1 hour','ok',$3::jsonb)"
        " ON CONFLICT (farm_id) DO UPDATE SET fetched_at = EXCLUDED.fetched_at, availability = 'ok', days = EXCLUDED.days", uuid.UUID(farm), age_h, json.dumps(days))


def day(offset: int, **over) -> dict:
    d = {"date": (TODAY + dt.timedelta(days=offset)).isoformat(), "tmin": 8.0, "tmax": 22.0, "rain_mm": 0.0, "wind_kmh": 8.0, "humidity_pct": 60.0, "icon": "sun"}
    return {**d, **over}
