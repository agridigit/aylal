"""Strict request bodies and response models of F4 (extra=forbid on every input; no storage key or URL is ever accepted)."""
import datetime as dt
import uuid
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

OBJECT_KEY_NAMES = frozenset({"file_key", "object_key", "url", "photo_key", "key_path"})
SystemKind = Literal["drip", "sprinkler", "pivot", "gravity"]


def is_object_ref_key(name: str) -> bool:
    return name in OBJECT_KEY_NAMES or name.endswith(("_key", "_url"))


def _refuse_object_refs(data: Any) -> Any:
    if isinstance(data, dict) and any(is_object_ref_key(str(k)) for k in data):
        raise ValueError("invalid_object_ref")
    return data


class IrrigationSystemInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: uuid.UUID | None = None
    kind: SystemKind
    emitter_flow_lph: float | None = Field(default=None, gt=0)
    emitter_spacing_m: float | None = Field(default=None, gt=0)
    row_spacing_m: float | None = Field(default=None, gt=0)
    pump_flow_m3h: float | None = Field(default=None, gt=0)
    sectors_count: int = Field(ge=1, le=50)
    efficiency: float | None = Field(default=None, gt=0, le=1)

    @model_validator(mode="before")
    @classmethod
    def _no_object_ref(cls, data: Any) -> Any:
        return _refuse_object_refs(data)

    @model_validator(mode="after")
    def _described(self) -> "IrrigationSystemInput":
        emitters = None not in (self.emitter_flow_lph, self.emitter_spacing_m, self.row_spacing_m)
        if self.pump_flow_m3h is None and not (self.kind == "drip" and emitters):
            raise ValueError("flow_required")
        return self


class IrrigationEventInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: uuid.UUID
    performed_on: dt.date
    sector_no: int | None = Field(default=None, ge=1)
    duration_min: int | None = Field(default=None, ge=1, le=1440)
    volume_m3: float | None = Field(default=None, gt=0)
    note: str = Field(default="", max_length=500)

    @model_validator(mode="before")
    @classmethod
    def _no_object_ref(cls, data: Any) -> Any:
        return _refuse_object_refs(data)

    @model_validator(mode="after")
    def _one_mode(self) -> "IrrigationEventInput":
        if (self.duration_min is None) == (self.volume_m3 is None):
            raise ValueError("exactly_one_of_duration_or_volume")
        return self


class WaterAnalysisInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: uuid.UUID
    ec_ds_m: float = Field(gt=0, le=100)
    analysed_on: dt.date
    water_source: str = Field(default="", max_length=80)

    @model_validator(mode="before")
    @classmethod
    def _no_object_ref(cls, data: Any) -> Any:
        return _refuse_object_refs(data)


class Assumption(BaseModel):
    key: str
    value: Any = None
    source: Literal["referential", "gateway", "computed", "default", "user", "sensor"]
    validated: bool | None = None


class SectorAdvice(BaseModel):
    sector_no: int
    minutes: int
    volume_m3: float | None = None


UnavailableReason = Literal[
    "no_system", "no_crop_coefficient", "no_root_depth", "no_depletion_fraction", "no_soil_reference", "no_soil_reserve",
    "no_effective_rain_method", "no_weather", "no_salinity_reference", "gateway_not_configured", "gateway_unreachable", "stale",
]
AdviceKind = Literal["irrigate", "postpone_rain", "no_need", "rainfed_stress", "unavailable"]


class Advice(BaseModel):
    parcel_id: uuid.UUID
    for_date: dt.date
    kind: AdviceKind
    total_minutes: int | None = None
    sectors: list[SectorAdvice] = Field(default_factory=list, max_length=50)
    net_need_mm: float | None = None
    leaching_fraction: float | None = None
    stress_level: Literal["none", "watch", "high"] | None = None
    confidence: Literal["high", "medium", "low"]
    assumptions: list[Assumption]
    unavailable_reason: UnavailableReason | None = None
    computed_at: dt.datetime
    is_last_known: bool = False
    ready_before_7: bool = False


class AdviceWorker(BaseModel):
    """Worker view of an Advice: no leaching_fraction; assumptions are the whitelisted keys of the worker view."""

    model_config = ConfigDict(extra="forbid")
    parcel_id: uuid.UUID
    for_date: dt.date
    kind: AdviceKind
    total_minutes: int | None = None
    sectors: list[SectorAdvice] = Field(default_factory=list, max_length=50)
    net_need_mm: float | None = None
    stress_level: Literal["none", "watch", "high"] | None = None
    confidence: Literal["high", "medium", "low"]
    assumptions: list[Assumption]
    unavailable_reason: str | None = None
    computed_at: dt.datetime
    is_last_known: bool = False
    ready_before_7: bool = False


class AdviceList(BaseModel):
    items: list[Advice | AdviceWorker] = Field(max_length=100)
    next_cursor: str | None = None
    to_irrigate_count: int = 0
    generated_at: dt.datetime
