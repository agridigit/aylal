"""SQLAlchemy models (specs/001-foundations/data-model.md). Schema is created by Alembic."""
import datetime as dt
import uuid
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    Text,
    func,
)
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
    vigor: Mapped[float | None]


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
    client_ip: Mapped[str | None] = mapped_column(Text)


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


# ---- F6 operations journal (alembic 0006; columns and constraints: specs/005-operations-journal/data-model.md) ----
def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True)


class CatalogVersion(Base):
    __tablename__ = "catalog_versions"
    id: Mapped[uuid.UUID] = _uuid_pk()
    imported_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    source_date: Mapped[dt.date] = mapped_column(Date)
    row_count: Mapped[int] = mapped_column(Integer)
    checksum: Mapped[str] = mapped_column(Text)


class PhytoProduct(Base):
    __tablename__ = "phyto_products"
    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(Text)
    name_normalized: Mapped[str] = mapped_column(Text)
    registration_no: Mapped[str | None] = mapped_column(Text)
    holder: Mapped[str | None] = mapped_column(Text)
    active_ingredients: Mapped[Any] = mapped_column(JSONB, server_default="[]")
    homologation_expires_on: Mapped[dt.date | None] = mapped_column(Date)
    expired_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    catalog_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("catalog_versions.id"))


class PhytoProductUse(Base):
    __tablename__ = "phyto_product_uses"
    id: Mapped[uuid.UUID] = _uuid_pk()
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("phyto_products.id", ondelete="CASCADE"))
    crop_slug: Mapped[str] = mapped_column(Text)
    target: Mapped[str | None] = mapped_column(Text)
    max_dose: Mapped[Any | None] = mapped_column(Numeric)
    dose_unit: Mapped[str | None] = mapped_column(Text)
    dar_days: Mapped[int | None] = mapped_column(Integer)
    max_applications: Mapped[int | None] = mapped_column(Integer)
    interval_days: Mapped[int | None] = mapped_column(Integer)


class Operation(Base):
    __tablename__ = "operations"
    id: Mapped[uuid.UUID] = _uuid_pk()
    farm_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"))
    type: Mapped[str] = mapped_column(Text)
    performed_on: Mapped[dt.date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(Text)
    author_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    operator_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    operator_name: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)
    season_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    quantity_total: Mapped[Any | None] = mapped_column(Numeric)
    quantity_unit: Mapped[str | None] = mapped_column(Text)
    label_photo_key: Mapped[str | None] = mapped_column(Text)  # server-generated only, never exposed
    product_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("phyto_products.id"))
    free_product_name: Mapped[str | None] = mapped_column(Text)
    dose: Mapped[Any | None] = mapped_column(Numeric)
    dose_unit: Mapped[str | None] = mapped_column(Text)
    product_lines: Mapped[Any] = mapped_column(JSONB, server_default="[]")
    validated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    validated_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    done_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    server_version: Mapped[int] = mapped_column(BigInteger, server_default="1")
    field_versions: Mapped[Any] = mapped_column(JSONB, server_default="{}")


class OperationParcel(Base):
    __tablename__ = "operation_parcels"
    id: Mapped[uuid.UUID] = _uuid_pk()
    farm_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    operation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    parcel_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    author_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    type: Mapped[str] = mapped_column(Text)
    performed_on: Mapped[dt.date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(Text)
    product_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    free_product_name: Mapped[str | None] = mapped_column(Text)
    allocated_quantity: Mapped[Any | None] = mapped_column(Numeric)
    allocated_dose: Mapped[Any | None] = mapped_column(Numeric)
    dose_unit: Mapped[str | None] = mapped_column(Text)
    area_ha_snapshot: Mapped[Any | None] = mapped_column(Numeric)
    crop_slug: Mapped[str | None] = mapped_column(Text)
    warnings: Mapped[Any] = mapped_column(JSONB, server_default="[]")
    parcel_archived_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))  # copied by trigger
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OperationReminder(Base):
    __tablename__ = "operation_reminders"
    id: Mapped[uuid.UUID] = _uuid_pk()
    farm_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    operation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    parcel_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    fire_on: Mapped[dt.date] = mapped_column(Date)
    state: Mapped[str] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RegistryEntry(Base):
    """Append-only (triggers registry_append_only); read through the view registry_current."""

    __tablename__ = "registry_entries"
    id: Mapped[uuid.UUID] = _uuid_pk()
    farm_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"))
    operation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    parcel_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    entry_kind: Mapped[str] = mapped_column(Text)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("registry_entries.id"))
    performed_on: Mapped[dt.date] = mapped_column(Date)
    parcel_name: Mapped[str] = mapped_column(Text)
    crop_name: Mapped[str | None] = mapped_column(Text)
    area_ha: Mapped[Any | None] = mapped_column(Numeric)
    product_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    product_name: Mapped[str] = mapped_column(Text)
    active_ingredients: Mapped[Any] = mapped_column(JSONB, server_default="[]")
    is_free_product: Mapped[bool] = mapped_column(Boolean, server_default="false")
    dose: Mapped[Any | None] = mapped_column(Numeric)
    dose_unit: Mapped[str | None] = mapped_column(Text)
    allocated_quantity: Mapped[Any | None] = mapped_column(Numeric)
    dar_days: Mapped[int | None] = mapped_column(Integer)
    max_dose: Mapped[Any | None] = mapped_column(Numeric)
    catalog_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    operator_name: Mapped[str] = mapped_column(Text)
    operator_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    warnings: Mapped[Any] = mapped_column(JSONB, server_default="[]")
    season_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    recorded_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.clock_timestamp())
    retain_until: Mapped[dt.date] = mapped_column(Date)


class OperationCorrection(Base):
    """Append-only (triggers registry_append_only)."""

    __tablename__ = "operation_corrections"
    id: Mapped[uuid.UUID] = _uuid_pk()
    farm_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"))
    operation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    field: Mapped[str] = mapped_column(Text)
    before: Mapped[Any | None] = mapped_column(JSONB)
    after: Mapped[Any | None] = mapped_column(JSONB)
    author_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    corrected_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.clock_timestamp())
    source: Mapped[str] = mapped_column(Text)
    registry_entry_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    server_version: Mapped[int | None] = mapped_column(BigInteger)


class LabelUpload(Base):
    __tablename__ = "label_uploads"
    id: Mapped[uuid.UUID] = _uuid_pk()  # the opaque label_photo_id handed to the client
    farm_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    object_key: Mapped[str] = mapped_column(Text)  # server-generated: farms/{farm_id}/labels/{uuid}
    consumed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ExportJob(Base):
    __tablename__ = "export_jobs"
    id: Mapped[uuid.UUID] = _uuid_pk()
    farm_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farms.id", ondelete="CASCADE"))
    requested_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    scope: Mapped[str] = mapped_column(Text)
    parcel_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    period_from: Mapped[dt.date] = mapped_column(Date)
    period_to: Mapped[dt.date] = mapped_column(Date)
    format: Mapped[str] = mapped_column(Text)
    lang: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(Text)
    file_keys: Mapped[Any | None] = mapped_column(JSONB)  # server only, never read from nor returned to a client
    sha256: Mapped[str | None] = mapped_column(Text)
    row_count: Mapped[int] = mapped_column(Integer, server_default="0")
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
