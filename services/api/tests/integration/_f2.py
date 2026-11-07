"""Shared F2 fixtures/helpers for integration tests (real PostgreSQL, no mocks)."""
import uuid

from tests.helpers import sql


def square(lon: float = -7.60, lat: float = 33.57, size: float = 0.002) -> dict:
    ring = [[lon, lat], [lon + size, lat], [lon + size, lat + size], [lon, lat + size], [lon, lat]]
    return {"type": "Polygon", "coordinates": [ring]}


def new_user() -> uuid.UUID:
    u = uuid.uuid4()
    sql("INSERT INTO users (id, phone_e164, status) VALUES ($1, $2, 'active')", u, f"+2126{uuid.uuid4().int % 10**8:08d}")
    return u


def add_field(farm: uuid.UUID, name: str = "Field", lon: float = -7.60) -> uuid.UUID:
    fid = uuid.uuid4()
    sql(
        "INSERT INTO parcels (id, farm_id, name, geometry, vigor) VALUES ($1, $2, $3, ST_SetSRID(ST_GeomFromGeoJSON($4), 4326), 0.5)",
        fid, farm, name, __import__("json").dumps(square(lon)),
    )
    return fid


def add_block(farm: uuid.UUID, field: uuid.UUID) -> uuid.UUID:
    bid = uuid.uuid4()
    sql(
        "INSERT INTO field_blocks (id, farm_id, field_id, name, kind, geometry) "
        "VALUES ($1, $2, $3, 'Block', 'block', (SELECT geometry FROM parcels WHERE id = $3))",
        bid, farm, field,
    )
    return bid


def reference_crop() -> uuid.UUID:
    return sql("SELECT id FROM crops WHERE farm_id IS NULL ORDER BY slug LIMIT 1")[0][0]


def add_custom_crop(farm: uuid.UUID) -> uuid.UUID:
    cid = uuid.uuid4()
    sql(
        "INSERT INTO crops (id, farm_id, slug, name_ary, name_ar, name_fr, cycle) VALUES ($1, $2, $3, 'x', 'x', 'x', 'annual')",
        cid, farm, f"custom-{cid}",
    )
    return cid


def add_season(farm: uuid.UUID, field: uuid.UUID, crop: uuid.UUID | None = None) -> uuid.UUID:
    sid = uuid.uuid4()
    sql(
        "INSERT INTO seasons (id, farm_id, field_id, crop_id, started_at) VALUES ($1, $2, $3, $4, current_date)",
        sid, farm, field, crop or reference_crop(),
    )
    return sid


def assign(farm: uuid.UUID, worker: uuid.UUID, field: uuid.UUID) -> None:
    sql("INSERT INTO worker_parcels (farm_id, user_id, parcel_id) VALUES ($1, $2, $3)", farm, worker, field)
