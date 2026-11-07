from fastapi import FastAPI

from app.routers import health

app = FastAPI(title="AYLAL API")
app.include_router(health.router, prefix="/v1")
