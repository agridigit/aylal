"""Purge of pending accounts that never consented (FR-012): only the phone number was ever stored."""
import datetime as dt

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
