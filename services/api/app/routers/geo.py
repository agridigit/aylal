"""Read-only geographic reference (regions, provinces, communes, point lookup)."""
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import current_user
from app.db.session import get_session

router = APIRouter(prefix="/geo")


async def _rows(session: AsyncSession, sql: str, **params: Any) -> list[dict[str, Any]]:
    return [dict(r) for r in (await session.execute(text(sql), params)).mappings().all()]


@router.get("/regions")
async def regions(
    _: uuid.UUID = Depends(current_user), session: AsyncSession = Depends(get_session)
) -> list[dict[str, Any]]:
    return await _rows(session, "SELECT id, name_ar, name_fr FROM geo_regions ORDER BY id")


@router.get("/provinces")
async def provinces(
    region: int | None = None,
    _: uuid.UUID = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    return await _rows(
        session,
        "SELECT id, name_ar, name_fr, parent_id AS region_id FROM geo_provinces"
        " WHERE (CAST(:r AS integer) IS NULL OR parent_id = :r) ORDER BY id",
        r=region,
    )


@router.get("/communes")
async def communes(
    province: int | None = None,
    _: uuid.UUID = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    return await _rows(
        session,
        "SELECT id, name_ar, name_fr, parent_id AS province_id FROM geo_communes"
        " WHERE (CAST(:p AS integer) IS NULL OR parent_id = :p) ORDER BY id",
        p=province,
    )


@router.get("/locate")
async def locate(
    lat: float = Query(ge=-90, le=90),
    lon: float = Query(ge=-180, le=180),
    _: uuid.UUID = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    found = await _rows(
        session,
        "SELECT id, name_ar, name_fr, parent_id AS province_id FROM geo_communes"
        " WHERE ST_Covers(geom, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)) ORDER BY id LIMIT 1",
        lat=lat,
        lon=lon,
    )
    if not found:
        raise HTTPException(status_code=404, detail="not_found")
    return found[0]
