"""Cycle de vie des données par utilisateur et par ferme (FR-021): purge dans la transaction de l'appelant."""
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.purge import purge_farm_monitoring_data


async def purge_member_monitoring(session: AsyncSession, farm_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Member removed or role changed: their summaries, preferences (push token included) and pending uploads go."""
    params = {"f": farm_id, "u": user_id}
    for table in ("daily_summaries", "notification_prefs", "observation_uploads"):
        await session.execute(text(f"DELETE FROM {table} WHERE farm_id = :f AND user_id = :u"), params)


async def purge_farm_monitoring(session: AsyncSession, farm_id: uuid.UUID) -> list[str]:
    """Deleted farm: every monitoring row of the farm; returns the object keys the caller must remove."""
    return await purge_farm_monitoring_data(session, farm_id)
