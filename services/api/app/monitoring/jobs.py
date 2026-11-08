"""Imagery job rows queued by the API; the worker (`backfill_parcel_vigor`) is the only one that processes them."""
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def queue_initial_history(session: AsyncSession, farm_id: uuid.UUID, parcel_id: uuid.UUID, user_id: uuid.UUID | None) -> None:
    """One 12-month history job per new parcel, in the creation transaction (no quota: creating a parcel never fails here)."""
    await session.execute(
        text("INSERT INTO monitoring_jobs (id, farm_id, parcel_id, kind, state, requested_by)"
             " VALUES (:i, :f, :p, 'backfill', 'queued', :u)"),
        {"i": uuid.uuid4(), "f": farm_id, "p": parcel_id, "u": user_id},
    )
