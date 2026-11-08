"""Dashboard cache (G2): the key carries farm, role, user (workers) and a fingerprint of the visible parcels, so two
scopes never share an entry; `data_version` is bumped when the farm data changes. Redis failures never break a request."""
import hashlib
import json
import uuid
from collections.abc import Iterable
from typing import Any

import redis.asyncio as redis

from app.config import get_settings

TTL_SECONDS = 60


def scope_fingerprint(parcel_ids: Iterable[uuid.UUID]) -> str:
    return hashlib.sha256(",".join(sorted(str(p) for p in parcel_ids)).encode()).hexdigest()


def dashboard_cache_key(
    farm_id: uuid.UUID, role: str, user_id: uuid.UUID, parcel_ids: Iterable[uuid.UUID], data_version: int
) -> str:
    """dash:{farm}:{role}:{user if worker}:{sha256(sorted visible ids)}:{data_version}; staff share by farm, role and scope."""
    parts = ["dash", str(farm_id), role]
    if role == "worker":
        parts.append(str(user_id))
    parts += [scope_fingerprint(parcel_ids), str(data_version)]
    return ":".join(parts)


def _client() -> Any:
    return redis.from_url(get_settings().redis_url)  # type: ignore[no-untyped-call]  # one client per call: callers live on different event loops


def _version_key(farm_id: uuid.UUID) -> str:
    return f"dashver:{farm_id}"


async def get_data_version(farm_id: uuid.UUID) -> int:
    client = _client()
    try:
        return int(await client.get(_version_key(farm_id)) or 0)
    except redis.RedisError:
        return 0
    finally:
        await client.aclose()


async def bump_data_version(farm_id: uuid.UUID) -> int:
    """Invalidate every cached view of the farm."""
    client = _client()
    try:
        return int(await client.incr(_version_key(farm_id)))
    finally:
        await client.aclose()


async def cache_get(key: str) -> dict[str, Any] | None:
    client = _client()
    try:
        raw = await client.get(key)
        return None if raw is None else dict(json.loads(raw))
    except redis.RedisError:
        return None
    finally:
        await client.aclose()


async def cache_set(key: str, value: dict[str, Any]) -> None:
    client = _client()
    try:
        await client.set(key, json.dumps(value, default=str), ex=TTL_SECONDS)
    except redis.RedisError:
        return
    finally:
        await client.aclose()
