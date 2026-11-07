"""Dev token, idempotent upload and conflict acknowledgement (contracts/openapi.yaml)."""
import uuid
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import WRITE_ROLES, current_user, farm_role, issue_token
from app.config import get_settings
from app.db.models import FarmMember, SyncConflict, TrialRecord
from app.db.session import get_session
from app.sync.apply import apply_op

router = APIRouter()
NOT_FOUND = HTTPException(status_code=404, detail="not_found")


class DevTokenRequest(BaseModel):
    user_id: uuid.UUID


class Op(BaseModel):
    op_id: uuid.UUID
    table: Literal["trial_records"]
    kind: Literal["put", "patch", "delete"]
    record_id: uuid.UUID
    farm_id: uuid.UUID | None = None
    base_version: int = Field(ge=0)
    fields: dict[str, Any] = Field(default_factory=dict)
    device_clock: str | None = None  # informational, never used to decide


class UploadBatch(BaseModel):
    ops: list[Op] = Field(max_length=500)


@router.post("/auth/dev-token")
async def dev_token(
    body: DevTokenRequest, session: AsyncSession = Depends(get_session)
) -> dict[str, str]:
    settings = get_settings()
    if settings.env not in ("dev", "test"):
        raise NOT_FOUND
    rows = (
        await session.execute(
            select(FarmMember.farm_id, FarmMember.role).where(FarmMember.user_id == body.user_id)
        )
    ).all()
    token, expires = issue_token(
        body.user_id,
        settings.jwt_secret,
        [str(f) for f, _ in rows],
        {str(f): r for f, r in rows},
    )
    return {"token": token, "expires_at": expires.isoformat()}


@router.post("/sync/upload")
async def upload(
    batch: UploadBatch,
    user_id: uuid.UUID = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, list[dict[str, Any]]]:
    results = []
    async with session.begin():  # one commit per batch: a cut connection never leaves a half batch
        for op in batch.ops:
            results.append(
                await apply_op(session, user_id, {**op.model_dump(), "author_id": user_id})
            )
    return {"results": results}


@router.post("/sync/conflicts/{conflict_id}/acknowledge", status_code=204)
async def acknowledge(
    conflict_id: uuid.UUID,
    user_id: uuid.UUID = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    async with session.begin():
        conflict = await session.get(SyncConflict, conflict_id)
        role = await farm_role(session, conflict.farm_id, user_id) if conflict else None
        if conflict is None or role is None:
            raise NOT_FOUND  # unknown and cross-farm are indistinguishable
        if role not in WRITE_ROLES:
            raise HTTPException(status_code=403, detail="forbidden")
        conflict.acknowledged_at = func.now()
        await session.flush()
        remaining = (
            await session.execute(
                select(func.count())
                .select_from(SyncConflict)
                .where(
                    SyncConflict.record_id == conflict.record_id,
                    SyncConflict.acknowledged_at.is_(None),
                )
            )
        ).scalar_one()
        if remaining == 0:
            await session.execute(
                update(TrialRecord)
                .where(TrialRecord.id == conflict.record_id)
                .values(has_conflict=False)
            )
    return Response(status_code=204)
