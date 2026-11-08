from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings, validate_external_gateways
from app.operations.body_limit import BodyLimitMiddleware
from app.routers import (
    account,
    alerts,
    auth,
    blocks,
    crops,
    dashboard,
    farms,
    fields,
    geo,
    health,
    me,
    operations,
    phyto_products,
    registry,
    seasons,
    summary,
    sync,
    vigor,
    zones,
)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    validate_external_gateways(get_settings())  # refuse to start on a weak or forbidden configuration (FR-027)
    yield


app = FastAPI(title="AYLAL API", lifespan=lifespan)
app.add_middleware(BodyLimitMiddleware)
app.include_router(health.router, prefix="/v1")
app.include_router(sync.router, prefix="/v1")
app.include_router(auth.router, prefix="/v1")
app.include_router(farms.router, prefix="/v1")
app.include_router(geo.router, prefix="/v1")
app.include_router(account.router, prefix="/v1")
app.include_router(me.router, prefix="/v1")
app.include_router(fields.router, prefix="/v1")
app.include_router(blocks.router, prefix="/v1")
app.include_router(seasons.router, prefix="/v1")
app.include_router(crops.router, prefix="/v1")
app.include_router(operations.router, prefix="/v1")
app.include_router(phyto_products.router, prefix="/v1")
app.include_router(phyto_products.farm_router, prefix="/v1")
app.include_router(registry.router, prefix="/v1")
app.include_router(dashboard.router, prefix="/v1")
app.include_router(alerts.router, prefix="/v1")
app.include_router(vigor.router, prefix="/v1")
app.include_router(zones.router, prefix="/v1")
app.include_router(summary.router, prefix="/v1")
