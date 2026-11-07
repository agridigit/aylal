from fastapi import FastAPI

from app.routers import health, sync

app = FastAPI(title="AYLAL API")
app.include_router(health.router, prefix="/v1")
app.include_router(sync.router, prefix="/v1")
