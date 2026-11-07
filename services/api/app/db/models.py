"""SQLAlchemy models (specs/001-foundations/data-model.md). Schema is created by Alembic."""
import datetime as dt
import uuid
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Numeric, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import UserDefinedType


class Polygon(UserDefinedType[Any]):
    cache_ok = True

    def get_col_spec(self, **kw: Any) -> str:
        return "geometry(Polygon, 4326)"


class Base(DeclarativeBase):
    pass


class Farm(Base):
    __tablename__ = "farms"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FarmMember(Base):
    __tablename__ = "farm_members"
    farm_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farms.id"), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    role: Mapped[str] = mapped_column(Text)


class Parcel(Base):
    __tablename__ = "parcels"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    farm_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farms.id"))
    name: Mapped[str] = mapped_column(Text)
    geometry: Mapped[Any] = mapped_column(Polygon())
    vigor: Mapped[float]


class TrialRecord(Base):
    __tablename__ = "trial_records"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    farm_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farms.id"))
    author_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    title: Mapped[str] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)
    quantity: Mapped[Any | None] = mapped_column(Numeric)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    server_version: Mapped[int] = mapped_column(BigInteger, default=1)
    field_versions: Mapped[dict[str, int]] = mapped_column(JSONB, default=dict)
    deleted_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    has_conflict: Mapped[bool] = mapped_column(Boolean, default=False)


class AppliedOp(Base):
    __tablename__ = "applied_ops"
    op_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    record_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    applied_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    result: Mapped[dict[str, Any]] = mapped_column(JSONB)


class SyncConflict(Base):
    __tablename__ = "sync_conflicts"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    farm_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farms.id"))
    record_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    field: Mapped[str] = mapped_column(Text)
    discarded_value: Mapped[Any] = mapped_column(JSONB)
    kept_value: Mapped[Any] = mapped_column(JSONB)
    discarded_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    base_version: Mapped[int] = mapped_column(BigInteger)
    server_version: Mapped[int] = mapped_column(BigInteger)
    detected_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    acknowledged_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
