"""Current user dependency and role lookup (the DB is the source of truth, not the token)."""
import uuid
from typing import Literal

from fastapi import Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.tokens import verify_token
from app.config import get_settings
from app.db.models import Farm, FarmMember, User
from app.db.session import sessionmaker

Role = Literal["owner", "manager", "worker"]
WRITE_ROLES = {"owner", "manager"}  # trial-record writers (a worker records only via F2 parcels)


async def current_user(authorization: str | None = Header(default=None)) -> uuid.UUID:
    if authorization and authorization.lower().startswith("bearer "):
        claims = verify_token(authorization[7:].strip(), get_settings().jwt_secret)
        if claims:
            user_id = uuid.UUID(claims["sub"])
            async with sessionmaker() as own:  # own session: never opens a transaction on the request's
                status = (await own.execute(select(User.status).where(User.id == user_id))).scalar_one_or_none()
            if status != "deletion_requested":  # a deletion request ends every session
                return user_id
    raise HTTPException(status_code=401, detail="unauthorized")


async def farm_role(session: AsyncSession, farm_id: uuid.UUID, user_id: uuid.UUID) -> str | None:
    result = await session.execute(
        select(FarmMember.role).join(Farm, Farm.id == FarmMember.farm_id).where(
            Farm.deleted_at.is_(None),
            FarmMember.farm_id == farm_id,
            FarmMember.user_id == user_id,
            FarmMember.removed_at.is_(None),
        )
    )
    return result.scalar_one_or_none()
