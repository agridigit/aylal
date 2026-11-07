"""Account deletion and personal-data export (R8). Everything is scoped to the authenticated user."""
import datetime as dt
import uuid
from typing import Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import current_user
from app.db.models import Farm, FarmMember, RefreshToken, User
from app.db.session import get_session
from app.domain.account_deletion import deletion_deadline, deletion_impact

router = APIRouter(prefix="/me")


class DeletionRequest(BaseModel):
    confirm: Literal[True]  # explicit confirmation: absent or false -> 422


@router.post("/deletion", status_code=202)
async def request_deletion(
    _: DeletionRequest, user_id: uuid.UUID = Depends(current_user), session: AsyncSession = Depends(get_session)
) -> dict[str, str]:
    now = dt.datetime.now(dt.UTC)
    await session.execute(
        update(User).where(User.id == user_id).values(status="deletion_requested", deletion_requested_at=now)
    )
    await session.execute(  # every device is signed out
        update(RefreshToken).where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None)).values(revoked_at=now)
    )
    await session.commit()
    return {"deletion_requested_at": now.isoformat(), "deletion_deadline": deletion_deadline(now).isoformat()}


@router.get("/deletion/impact")
async def deletion_impact_route(
    user_id: uuid.UUID = Depends(current_user), session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    mine = (
        await session.execute(
            select(Farm.id, Farm.name, FarmMember.role)
            .join(FarmMember, FarmMember.farm_id == Farm.id)
            .where(FarmMember.user_id == user_id, FarmMember.removed_at.is_(None), Farm.deleted_at.is_(None))
            .order_by(Farm.created_at)
        )
    ).all()
    counts = dict(
        (
            await session.execute(
                select(FarmMember.farm_id, func.count())
                .where(
                    FarmMember.farm_id.in_([f for f, _, _ in mine]),
                    FarmMember.user_id != user_id,
                    FarmMember.removed_at.is_(None),
                )
                .group_by(FarmMember.farm_id)
            )
        ).all()
    )
    farms = [
        {"farm_id": str(f), "name": n, "role": r, "other_members": counts.get(f, 0)} for f, n, r in mine
    ]
    return {"owned_farms": deletion_impact(farms)}


@router.post("/export", status_code=202)
async def request_export(_: uuid.UUID = Depends(current_user)) -> dict[str, str]:
    return {"export_id": str(uuid.uuid4())}
