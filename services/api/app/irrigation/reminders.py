"""Morning reminders (G1): recipients are ACTIVE members (removed_at IS NULL, replayed at every generation) and each gets the
irrigated parcels THEY can see. The payload carries no analysis, soil or salinity datum: the advice itself is read in the app."""
import datetime as dt
import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.farm_context import FarmContext
from app.irrigation.access import visible_parcels

_MEMBERS = (
    "SELECT m.user_id, m.role FROM farm_members m JOIN farms f ON f.id = m.farm_id WHERE m.farm_id = :farm AND m.removed_at IS NULL"
    " AND f.deleted_at IS NULL ORDER BY m.user_id"
)
_IRRIGATED = "SELECT id FROM parcels WHERE farm_id = :farm AND id = ANY(:ids) AND irrigation IS DISTINCT FROM 'rainfed'"


async def reminder_targets(session: AsyncSession, farm_id: uuid.UUID, for_date: dt.date) -> list[dict[str, Any]]:
    """One target per (active member, visible irrigated parcel)."""
    targets: list[dict[str, Any]] = []
    for member in (await session.execute(text(_MEMBERS), {"farm": farm_id})).all():
        visible = await visible_parcels(FarmContext(farm_id, member.user_id, member.role, session))
        irrigated = {r[0] for r in (await session.execute(text(_IRRIGATED), {"farm": farm_id, "ids": visible})).all()} if visible else set()
        if not irrigated:  # an active member with nothing to irrigate stays listed (no parcel, no content)
            targets.append({"user_id": member.user_id, "role": member.role, "farm_id": farm_id, "parcel_id": None, "for_date": for_date})
        targets += [
            {"user_id": member.user_id, "role": member.role, "farm_id": farm_id, "parcel_id": p, "for_date": for_date}
            for p in sorted(irrigated, key=str)
        ]
    return targets


def reminder_payload(target: dict[str, Any], role: str) -> dict[str, Any]:
    """Minimal and identical in shape for every role: a key for the text and the parcel; nothing derived from the advice."""
    payload = {"message_key": "irrigation.reminder.morning", "for_date": target["for_date"].isoformat(), "audience": role}
    if target["parcel_id"] is not None:
        payload["parcel_id"] = str(target["parcel_id"])
    return payload
