"""Deterministic seed (T056): trial account, 1 farm, 50 parcels. Idempotent."""
import uuid
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_NS = uuid.UUID("a71a1000-0000-4000-8000-000000000001")
_PARCEL_COUNT = 50
_ORIGIN_LON, _ORIGIN_LAT, _STEP = -8.0, 31.63, 0.002


@dataclass(frozen=True)
class SeedParcel:
    id: uuid.UUID
    farm_id: uuid.UUID
    name: str
    wkt: str
    vigor: float


@dataclass(frozen=True)
class SeedData:
    user_id: uuid.UUID
    farm_id: uuid.UUID
    farm_name: str
    members: dict[uuid.UUID, str]
    parcels: tuple[SeedParcel, ...]


def _square(index: int) -> str:
    lon = _ORIGIN_LON + (index % 10) * _STEP
    lat = _ORIGIN_LAT + (index // 10) * _STEP
    w = _STEP * 0.8
    pts = [(lon, lat), (lon + w, lat), (lon + w, lat + w), (lon, lat + w), (lon, lat)]
    return "POLYGON((" + ", ".join(f"{x:.6f} {y:.6f}" for x, y in pts) + "))"


def build_seed() -> SeedData:
    user_id = uuid.uuid5(_NS, "user:trial")
    farm_id = uuid.uuid5(_NS, "farm:trial")
    parcels = tuple(
        SeedParcel(
            id=uuid.uuid5(_NS, f"parcel:{i}"),
            farm_id=farm_id,
            name=f"Parcel {i + 1:02d}",
            wkt=_square(i),
            vigor=round(((i * 37) % 101) / 100, 2),
        )
        for i in range(_PARCEL_COUNT)
    )
    return SeedData(user_id, farm_id, "Trial farm", {user_id: "owner"}, parcels)


async def seed(session: AsyncSession) -> SeedData:
    data = build_seed()
    await session.execute(
        text("INSERT INTO farms (id, name) VALUES (:id, :name) ON CONFLICT (id) DO NOTHING"),
        {"id": data.farm_id, "name": data.farm_name},
    )
    for user_id, role in data.members.items():
        await session.execute(
            text(
                "INSERT INTO farm_members (farm_id, user_id, role) VALUES (:f, :u, :r) "
                "ON CONFLICT (farm_id, user_id) DO NOTHING"
            ),
            {"f": data.farm_id, "u": user_id, "r": role},
        )
    for p in data.parcels:
        await session.execute(
            text(
                "INSERT INTO parcels (id, farm_id, name, geometry, vigor) "
                "VALUES (:id, :f, :name, ST_GeomFromText(:wkt, 4326), :vigor) ON CONFLICT (id) DO NOTHING"
            ),
            {"id": p.id, "f": p.farm_id, "name": p.name, "wkt": p.wkt, "vigor": p.vigor},
        )
    await session.commit()
    return data
