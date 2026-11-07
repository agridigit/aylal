from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.routers import account, auth, farms, geo, health, me, sync


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    get_settings()  # refuse to start on a weak or forbidden configuration (FR-027)
    yield


app = FastAPI(title="AYLAL API", lifespan=lifespan)
app.include_router(health.router, prefix="/v1")
app.include_router(sync.router, prefix="/v1")
app.include_router(auth.router, prefix="/v1")
app.include_router(farms.router, prefix="/v1")
app.include_router(geo.router, prefix="/v1")
app.include_router(account.router, prefix="/v1")
app.include_router(me.router, prefix="/v1")
