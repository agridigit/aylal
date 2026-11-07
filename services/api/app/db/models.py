"""SQLAlchemy models (specs/001-foundations/data-model.md). Schema is created by Alembic."""
import datetime as dt
import uuid
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, ForeignKeyConstraint, Integer, Numeric, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import UserDefinedType


class Polygon(UserDefinedType[Any]):
    cache_ok = True

    def get_col_spec(self, **kw: Any) -> str:
        return "geometry(Polygon, 4326)"


class Base(DeclarativeBase):
    pass


class Point(UserDefinedType[Any]):
    cache_ok = True

    def get_col_spec(self, **kw: Any) -> str:
        return "geometry(Point, 4326)"


class Farm(Base):
    __tablename__ = "farms"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    owner_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    location: Mapped[Any | None] = mapped_column(Point())
    commune_id: Mapped[int | None] = mapped_column(ForeignKey("geo_communes.id"))
    area_ha: Mapped[Any | None] = mapped_column(Numeric)
    deleted_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))


class FarmMember(Base):
    __tablename__ = "farm_members"
    farm_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farms.id"), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    role: Mapped[str] = mapped_column(Text)
    added_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    removed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))


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


class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    phone_e164: Mapped[str] = mapped_column(Text, unique=True)
    display_name: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default="pending")
    onboarding_step: Mapped[str | None] = mapped_column(Text)
    deletion_requested_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Consent(Base):
    __tablename__ = "consents"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    purpose: Mapped[str] = mapped_column(Text)
    text_version: Mapped[str] = mapped_column(Text)
    granted_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    withdrawn_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))


class OtpChallenge(Base):
    __tablename__ = "otp_challenges"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    phone_e164: Mapped[str] = mapped_column(Text)
    code_hash: Mapped[str] = mapped_column(Text)
    channel: Mapped[str] = mapped_column(Text, default="sms")
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    last_sent_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    consumed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    token_hash: Mapped[str] = mapped_column(Text, unique=True)
    device_id: Mapped[str | None] = mapped_column(Text)
    family_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    rotated_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WorkerParcel(Base):
    __tablename__ = "worker_parcels"
    __table_args__ = (
        ForeignKeyConstraint(["farm_id", "user_id"], ["farm_members.farm_id", "farm_members.user_id"]),
        ForeignKeyConstraint(["farm_id", "parcel_id"], ["parcels.farm_id", "parcels.id"]),
    )
    farm_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    parcel_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    assigned_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Invitation(Base):
    __tablename__ = "invitations"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    farm_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farms.id"))
    phone_e164: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default="pending")
    invited_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GeoRegion(Base):
    __tablename__ = "geo_regions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name_ar: Mapped[str] = mapped_column(Text)
    name_fr: Mapped[str] = mapped_column(Text)


class GeoProvince(Base):
    __tablename__ = "geo_provinces"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name_ar: Mapped[str] = mapped_column(Text)
    name_fr: Mapped[str] = mapped_column(Text)
    parent_id: Mapped[int] = mapped_column(ForeignKey("geo_regions.id"))


class GeoCommune(Base):
    __tablename__ = "geo_communes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name_ar: Mapped[str] = mapped_column(Text)
    name_fr: Mapped[str] = mapped_column(Text)
    parent_id: Mapped[int] = mapped_column(ForeignKey("geo_provinces.id"))
