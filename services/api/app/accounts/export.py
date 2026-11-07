"""Complete personal-data export (FR-026): only what belongs to the user, never hashes or others' data."""
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Consent, Farm, FarmMember, TrialRecord, User


async def build_export(session: AsyncSession, user_id: uuid.UUID) -> dict[str, Any]:
    user = (await session.execute(select(User).where(User.id == user_id))).scalar_one()
    consents = (
        await session.execute(select(Consent).where(Consent.user_id == user_id).order_by(Consent.granted_at))
    ).scalars().all()
    farms = (
        await session.execute(
            select(FarmMember.farm_id, FarmMember.role)
            .join(Farm, Farm.id == FarmMember.farm_id)
            .where(FarmMember.user_id == user_id, FarmMember.removed_at.is_(None), Farm.deleted_at.is_(None))
            .order_by(FarmMember.added_at)
        )
    ).all()
    records = (
        await session.execute(
            select(TrialRecord)
            .where(TrialRecord.author_id == user_id, TrialRecord.deleted_at.is_(None))
            .order_by(TrialRecord.created_at)
        )
    ).scalars().all()
    return {
        "profile": {"phone": user.phone_e164, "display_name": user.display_name, "language": user.language},
        "consents": [
            {
                "purpose": c.purpose, "text_version": c.text_version,
                "granted_at": c.granted_at.isoformat(),
                "withdrawn_at": c.withdrawn_at.isoformat() if c.withdrawn_at else None,
            }
            for c in consents
        ],
        "farms": [{"id": str(f), "role": r} for f, r in farms],
        "records": [
            {
                "id": str(r.id), "farm_id": str(r.farm_id), "title": r.title, "note": r.note,
                "quantity": None if r.quantity is None else float(r.quantity),
                "created_at": r.created_at.isoformat(),
            }
            for r in records
        ],
    }
