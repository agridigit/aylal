"""Strict request bodies of the F6 routes (OperationInput itself is generated from the Zod schema)."""
import datetime as dt
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.generated.models import DoseUnit, OperationInput, ProductLine, Status

__all__ = ["FreeProductRequest", "OperationInput", "OperationPatch", "ParseRequest", "RegistryExportRequest", "RescheduleRequest"]


class OperationPatch(BaseModel):
    """Correction of an operation (owner/manager). No storage key exists: a photo is named by `label_photo_id`."""

    model_config = ConfigDict(extra="forbid")
    performed_on: dt.date | None = None
    product_id: uuid.UUID | None = None
    free_product_name: str | None = Field(default=None, min_length=1, max_length=80)
    product_lines: list[ProductLine] | None = Field(default=None, max_length=5)
    dose: float | None = Field(default=None, gt=0, le=100000)
    dose_unit: DoseUnit | None = None
    quantity_total: float | None = Field(default=None, gt=0, le=100000)
    quantity_unit: str | None = Field(default=None, min_length=1, max_length=20)
    operator_name: str | None = Field(default=None, max_length=80)
    note: str | None = Field(default=None, max_length=500)
    label_photo_id: uuid.UUID | None = None
    status: Status | None = None  # ignored: the server decides the status


class RescheduleRequest(BaseModel):
    """New date of a planned operation; nothing else is accepted (the status is the server's)."""

    model_config = ConfigDict(extra="forbid")
    performed_on: dt.date


class ParseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=500)


class FreeProductRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=80)


class RegistryExportRequest(BaseModel):
    """Export of the registry. No file key or URL is ever accepted: the server names the files."""

    model_config = ConfigDict(extra="forbid")
    period_from: dt.date
    period_to: dt.date
    format: Literal["pdf", "xlsx", "both"]
    scope: Literal["farm", "parcel"]
    lang: Literal["fr", "ar", "ary"]
    parcel_id: uuid.UUID | None = None
