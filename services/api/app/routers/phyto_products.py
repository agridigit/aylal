"""Phyto product catalogue (global reference) and farm-scoped free products (F6)."""
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import current_user
from app.auth.farm_context import FarmContext, require
from app.db.session import get_session
from app.operations.schemas import FreeProductRequest

router = APIRouter(prefix="/phyto-products")
farm_router = APIRouter(prefix="/farms/{farm_id}/phyto-products")
_REQUIRE_PHYTO_PRODUCT_CREATE_FREE = require("phyto_product.create_free")


@router.get("")
async def search_products(
    q: str = Query(default="", max_length=80), crop: str | None = Query(default=None, max_length=80),
    limit: int = Query(default=20, ge=1, le=50),
    _: uuid.UUID = Depends(current_user), session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    needle = q.strip().lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    rows = (
        await session.execute(
            text(
                "SELECT p.id, p.name, p.registration_no, p.holder, p.active_ingredients, p.expired_at IS NOT NULL AS expired"
                " FROM phyto_products p WHERE p.expired_at IS NULL AND (p.name_normalized LIKE :prefix ESCAPE '\\'"
                " OR p.name_normalized LIKE :infix ESCAPE '\\' OR EXISTS (SELECT 1 FROM jsonb_array_elements(p.active_ingredients) a"
                " WHERE lower(a->>'name') LIKE :infix ESCAPE '\\'))"
                " AND (CAST(:crop AS text) IS NULL OR EXISTS (SELECT 1 FROM phyto_product_uses u WHERE u.product_id = p.id"
                " AND u.crop_slug = CAST(:crop AS text))) ORDER BY p.name_normalized LIMIT :n"
            ),
            {"prefix": needle + "%", "infix": "%" + needle + "%", "crop": crop, "n": limit},
        )
    ).mappings().all()
    version = (
        await session.execute(text("SELECT id, source_date FROM catalog_versions ORDER BY imported_at DESC LIMIT 1"))
    ).mappings().first()
    return {
        "items": [{**dict(r), "id": str(r["id"])} for r in rows],
        "catalog_version": None if version is None else {"id": str(version["id"]), "source_date": version["source_date"].isoformat()},
    }


@farm_router.post("/free")
async def create_free_product(body: FreeProductRequest, _: FarmContext = Depends(_REQUIRE_PHYTO_PRODUCT_CREATE_FREE)) -> dict[str, Any]:
    """A free product is only a name carried by the operation: it is never checked against the catalogue."""
    return {"name": " ".join(body.name.split()), "is_free": True}
