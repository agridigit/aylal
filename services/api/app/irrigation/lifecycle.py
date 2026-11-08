"""Cycle de vie des données F4 par utilisateur et par ferme (FR-021): purge dans la transaction de l'appelant."""
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def purge_member_irrigation(session: AsyncSession, farm_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Member removed or role changed: their reminder log goes. Events and their `author_id` stay (anonymised only when the
    ACCOUNT is deleted, by the F6 maintenance function)."""
    await session.execute(text("DELETE FROM irrigation_notification_log WHERE farm_id = :f AND user_id = :u"), {"f": farm_id, "u": user_id})


async def purge_farm_irrigation(session: AsyncSession, farm_id: uuid.UUID) -> None:
    """Deleted farm: the derived and per-user rows of the farm. Events and analyses go with the farm (ON DELETE CASCADE), never
    through an explicit DELETE here."""
    params = {"f": farm_id}
    for table in (
        "irrigation_notification_log", "irrigation_jobs", "irrigation_plans", "water_balance_days", "moisture_corrections",
        "irrigation_applied", "irrigation_system_versions", "irrigation_systems",
    ):
        await session.execute(text(f"DELETE FROM {table} WHERE farm_id = :f"), params)
