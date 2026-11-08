"""Purge of pending accounts that never consented (FR-012): only the phone number was ever stored."""
import datetime as dt
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

PENDING_TTL = dt.timedelta(hours=24)

_ELIGIBLE = """
    SELECT u.id FROM users u
    WHERE u.status = 'pending' AND u.created_at < :cutoff AND u.display_name IS NULL
      AND NOT EXISTS (SELECT 1 FROM consents c WHERE c.user_id = u.id AND c.withdrawn_at IS NULL)
      AND NOT EXISTS (SELECT 1 FROM farm_members m WHERE m.user_id = u.id)
      AND NOT EXISTS (SELECT 1 FROM farms f WHERE f.owner_id = u.id)
"""


async def purge_pending_accounts(session: AsyncSession, now: dt.datetime) -> int:
    params = {"cutoff": now - PENDING_TTL}
    for table in ("refresh_tokens", "consents"):
        await session.execute(text(f"DELETE FROM {table} WHERE user_id IN ({_ELIGIBLE})"), params)
    result = await session.execute(text(f"DELETE FROM users WHERE id IN ({_ELIGIBLE})"), params)
    return int(result.rowcount or 0)  # type: ignore[attr-defined]


_FARM_TABLES = (
    "zone_observations", "attention_zones", "vigor_maps", "parcel_vigor_points", "parcel_status_items", "parcel_status",
    "alerts", "monitoring_jobs", "daily_summaries", "notification_prefs", "observation_uploads", "farm_weather",
)


async def purge_farm_monitoring_data(session: AsyncSession, farm_id: uuid.UUID) -> list[str]:
    """F3: erase every monitoring row of a farm and return the object keys (maps, photos) to remove from storage."""
    params = {"f": farm_id}
    keys: list[str] = []
    for query in (
        "SELECT map_key FROM vigor_maps WHERE farm_id = :f",
        "SELECT photo_key FROM zone_observations WHERE farm_id = :f AND photo_key IS NOT NULL",
        "SELECT object_key FROM observation_uploads WHERE farm_id = :f",
    ):
        keys += [r[0] for r in (await session.execute(text(query), params)).all()]
    for table in _FARM_TABLES:
        await session.execute(text(f"DELETE FROM {table} WHERE farm_id = :f"), params)
    return keys


async def purge_user_monitoring_data(session: AsyncSession, user_id: uuid.UUID) -> list[str]:
    """F3: erase the personal monitoring data of a user; returns the photo keys to remove from storage."""
    params = {"u": user_id}
    keys = [r[0] for r in (await session.execute(text("SELECT photo_key FROM zone_observations WHERE author_id = :u AND photo_key IS NOT NULL"), params)).all()]
    keys += [r[0] for r in (await session.execute(text("SELECT object_key FROM observation_uploads WHERE user_id = :u"), params)).all()]
    await session.execute(text("DELETE FROM zone_observations WHERE author_id = :u"), params)
    for table in ("daily_summaries", "notification_prefs", "observation_uploads"):
        await session.execute(text(f"DELETE FROM {table} WHERE user_id = :u"), params)
    return keys
