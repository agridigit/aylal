"""Shared F3 fixtures/helpers for integration tests (real PostgreSQL, no mocks).

Rows are seeded with plain SQL against the columns of specs/006-dashboard-monitoring/data-model.md: before the
migration the failure is UndefinedTable, which is the right reason.
"""
import datetime as dt
import json
import socket
import uuid
from urllib.parse import urlparse

import pytest

from tests.helpers import auth, sql
from tests.integration._f2 import add_field, assign, new_user  # noqa: F401  (re-exported)

NOW = dt.datetime.now(dt.UTC)
TODAY = dt.date.today()
NOT_FOUND = {"detail": "not_found"}
COLORS = {0: "red", 1: "orange", 2: "green", 3: "orange", 5: "red"}  # others green


def seed_status(farm, parcel, color, rank=0, reliability="ok"):
    sql("INSERT INTO parcel_status (parcel_id, farm_id, color, reason_key, reason_params, rank, computed_at, data_age_at, imagery_reliability)"
        " VALUES ($1,$2,$3,'status.fixture','{}'::jsonb,$4,now(),now(),$5)", parcel, farm, color, rank, reliability)


def set_status(parcel, color):
    sql("UPDATE parcel_status SET color=$2, computed_at=now() WHERE parcel_id=$1", parcel, color)


def seed_alert(farm, parcel, *, type_="frost", severity="critical", status="active", day=None):
    aid = uuid.uuid4()
    day = day or TODAY + dt.timedelta(days=2)
    sql("INSERT INTO alerts (id, farm_id, parcel_id, crop_slug, type, severity, source, status, forecast_day, reason_key, reason_params, revision, dedup_key)"
        " VALUES ($1,$2,$3,'fixture_sensitive',$4,$5,'forecast',$6,$7,'alert.fixture','{}'::jsonb,1,$8)",
        aid, farm, parcel, type_, severity, status, day, f"dk-{aid}")
    return aid


def seed_zone(farm, parcel, status="open"):
    zid = uuid.uuid4()
    poly = json.dumps({"type": "Polygon", "coordinates": [[[-7.60, 33.57], [-7.599, 33.57], [-7.599, 33.571], [-7.60, 33.571], [-7.60, 33.57]]]})
    pt = json.dumps({"type": "Point", "coordinates": [-7.5995, 33.5705]})
    sql("INSERT INTO attention_zones (id, farm_id, parcel_id, geometry, centroid, detected_on, drop_score, area_ha, status, reason_key)"
        " VALUES ($1,$2,$3,ST_SetSRID(ST_GeomFromGeoJSON($4),4326),ST_SetSRID(ST_GeomFromGeoJSON($5),4326),$6,0.3,0.1,$7,'zone.fixture')",
        zid, farm, parcel, poly, pt, TODAY, status)
    return zid


def seed_observation(farm, zone, parcel, author, note="fixture"):
    oid = uuid.uuid4()
    sql("INSERT INTO zone_observations (id, farm_id, zone_id, parcel_id, author_id, note, created_at) VALUES ($1,$2,$3,$4,$5,$6,now())",
        oid, farm, zone, parcel, author, note)
    return oid


def seed_status_item(farm, parcel, source="weather_alert"):
    iid = uuid.uuid4()
    sql("INSERT INTO parcel_status_items (id, farm_id, parcel_id, source, severity, reason_key, reason_params, source_ref, observed_at)"
        " VALUES ($1,$2,$3,$4,'act','status.fixture','{}'::jsonb,$5,now())", iid, farm, parcel, source, uuid.uuid4())
    return iid


def seed_scene(farm, parcel, acquired_on=None):
    """A valid vigor point and its map; returns (scene_id, map_id)."""
    scene, mid, tile = uuid.uuid4(), uuid.uuid4(), "31SBU"
    on = acquired_on or TODAY - dt.timedelta(days=3)
    sql("INSERT INTO imagery_tiles (tile_id, last_ingested_on) VALUES ($1,$2) ON CONFLICT DO NOTHING", tile, on)
    sql("INSERT INTO imagery_scenes (id, tile_id, acquired_on, cloud_pct_scene, raster_key, ingested_at) VALUES ($1,$2,$3,5,$4,now())",
        scene, tile, on, f"rasters/{scene}")
    sql("INSERT INTO parcel_vigor_points (id, farm_id, parcel_id, scene_id, acquired_on, vigor_mean, plant_moisture_mean, clear_pct, reliability)"
        " VALUES ($1,$2,$3,$4,$5,0.6,0.4,95,'ok')", uuid.uuid4(), farm, parcel, scene, on)
    sql("INSERT INTO vigor_maps (id, farm_id, parcel_id, scene_id, acquired_on, map_key, bounds) VALUES ($1,$2,$3,$4,$5,$6,'{}'::jsonb)",
        mid, farm, parcel, scene, on, f"farms/{farm}/vigor/{uuid.uuid4()}.png")
    return scene, mid


def seed_summary(farm, user, day=None):
    sid = uuid.uuid4()
    sql("INSERT INTO daily_summaries (id, farm_id, user_id, summary_date, locale, payload, created_at)"
        " VALUES ($1,$2,$3,$4,'fr','{\"items\":[]}'::jsonb,now())", sid, farm, user, day or TODAY)
    return sid


def seed_prefs(farm, user, token="push-token-fixture"):
    sql("INSERT INTO notification_prefs (farm_id, user_id, summary_hour, alerts_enabled, push_token) VALUES ($1,$2,7,true,$3)", farm, user, token)


def seed_worker_rows(farm, parcel, worker):
    """One row per synchronised table for a parcel; returns ids."""
    z = seed_zone(farm, parcel)
    scene, mid = seed_scene(farm, parcel)
    return dict(alert=seed_alert(farm, parcel), zone=z, observation=seed_observation(farm, z, parcel, worker),
                item=seed_status_item(farm, parcel), scene=scene, map=mid)


@pytest.fixture
def world3(make_farm):
    """Farm A with 10 parcels, 3 assigned to the worker (p0..p2), p5 red but invisible to the worker."""
    owner, manager, worker, worker2, owner_b, outsider = (new_user() for _ in range(6))
    farm_a = make_farm({owner: "owner", manager: "manager", worker: "worker", worker2: "worker"})
    farm_b = make_farm({owner_b: "owner"})
    p = [add_field(farm_a, f"P{i}", lon=-7.60 + i * 0.01) for i in range(10)]
    b1 = add_field(farm_b, "B1", lon=-7.5)
    for i in range(3):
        assign(farm_a, worker, p[i])
    for i, parcel in enumerate(p):
        seed_status(farm_a, parcel, COLORS.get(i, "green"), rank=i)
    seed_status(farm_b, b1, "red")
    return dict(owner=owner, manager=manager, worker=worker, worker2=worker2, owner_b=owner_b, outsider=outsider,
                farm_a=farm_a, farm_b=farm_b, p=p, b1=b1, a1=p[0], hidden=p[5])


def routes(farm, parcel, alert, zone, scene):
    """Every F3 farm route as (name, method, path, json body) addressed on `farm`."""
    f = f"/v1/farms/{farm}"
    v = f"{f}/parcels/{parcel}/vigor"
    return [
        ("dashboard", "GET", f"{f}/dashboard", None),
        ("weather", "GET", f"{f}/weather", None),
        ("alerts", "GET", f"{f}/alerts", None),
        ("alert_dismiss", "POST", f"{f}/alerts/{alert}/dismiss", None),
        ("status", "GET", f"{f}/parcels/{parcel}/status", None),
        ("vigor", "GET", v, None),
        ("compare", "GET", f"{v}/compare", None),
        ("map", "GET", f"{v}/scenes/{scene}/map", None),
        ("reprocess", "POST", f"{v}/reprocess", None),
        ("zones", "GET", f"{f}/zones", None),
        ("zone_dismiss", "POST", f"{f}/zones/{zone}/dismiss", None),
        ("photo", "POST", f"{f}/zones/{zone}/observations/photo", None),
        ("observation", "POST", f"{f}/zones/{zone}/observations", {"id": str(uuid.uuid4()), "note": "x"}),
        ("summary", "GET", f"{f}/summary/today", None),
        ("settings", "PUT", f"{f}/summary/settings", {"summary_hour": 7, "alerts_enabled": True}),
    ]


def call(client, token, method, path, body=None):
    return client.request(method, path, headers=auth(token), json=body)


def sync_obs(farm, zone, note="x", rid=None, **extra):
    """A /v1/sync/upload op creating a zone observation."""
    rid = rid or uuid.uuid4()
    return {"op_id": str(uuid.uuid4()), "table": "zone_observations", "kind": "put", "record_id": str(rid), "farm_id": str(farm),
            "base_version": 0, "fields": {"zone_id": str(zone), "note": note, **extra}}


def sync_post(client, token, ops):
    return client.post("/v1/sync/upload", json={"ops": ops}, headers=auth(token))


def flush_redis():
    """FLUSHDB over a raw RESP socket (no redis client library needed in the test)."""
    from app.config import get_settings

    u = urlparse(get_settings().redis_url)
    with socket.create_connection((u.hostname or "redis", u.port or 6379), timeout=3) as s:
        s.sendall(b"*1\r\n$7\r\nFLUSHDB\r\n")
        assert s.recv(16).startswith(b"+OK")


def keys_of(obj):
    """All dict keys, recursively."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from keys_of(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from keys_of(v)
