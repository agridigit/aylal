"""Shared Redis rate limiter (fixed window). Over the limit -> 429 with Retry-After (G5)."""
import redis.asyncio as redis
from fastapi import HTTPException

from app.config import get_settings


async def check_rate_limit(key: str, limit: int, window_seconds: int = 3600) -> None:
    """Count one hit on `key`; raise 429 + Retry-After once more than `limit` hits fall in the window."""
    client = redis.from_url(get_settings().redis_url)  # one client per call: callers live on different event loops
    try:
        async with client.pipeline(transaction=True) as pipe:
            pipe.incr(key)
            pipe.expire(key, window_seconds, nx=True)
            pipe.ttl(key)
            hits, _, ttl = await pipe.execute()
    except redis.RedisError as e:
        raise HTTPException(status_code=503, detail={"code": "rate_limit_unavailable"}) from e
    finally:
        await client.aclose()
    if hits > limit:
        raise HTTPException(
            status_code=429, detail={"code": "rate_limited"}, headers={"Retry-After": str(max(1, int(ttl)))}
        )
