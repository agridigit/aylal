"""GET /v1/health: unauthenticated liveness of the API and its dependencies."""
import asyncio
from typing import Literal
from urllib.parse import urlparse

import asyncpg  # type: ignore[import-untyped]
from fastapi import APIRouter, Response
from pydantic import BaseModel

from app.config import get_settings

router = APIRouter()
TIMEOUT_S = 2.0
Check = Literal["ok", "down"]


class Health(BaseModel):
    status: Literal["ok", "degraded"]
    checks: dict[str, Check]


async def _check_db(url: str) -> Check:
    try:
        conn = await asyncpg.connect(url, timeout=TIMEOUT_S)
        try:
            await conn.execute("SELECT 1")
        finally:
            await conn.close()
        return "ok"
    except Exception:
        return "down"


async def _check_redis(url: str) -> Check:
    parsed = urlparse(url)
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(parsed.hostname or "redis", parsed.port or 6379), TIMEOUT_S
        )
        try:
            writer.write(b"PING\r\n")
            await writer.drain()
            reply = await asyncio.wait_for(reader.readline(), TIMEOUT_S)
        finally:
            writer.close()
        return "ok" if reply.startswith(b"+PONG") else "down"
    except Exception:
        return "down"


@router.get("/health", response_model=Health)
async def health(response: Response) -> Health:
    settings = get_settings()
    db, redis = await asyncio.gather(_check_db(settings.database_url), _check_redis(settings.redis_url))
    checks: dict[str, Check] = {"db": db, "redis": redis}
    healthy = all(v == "ok" for v in checks.values())
    if not healthy:
        response.status_code = 503
    return Health(status="ok" if healthy else "degraded", checks=checks)
