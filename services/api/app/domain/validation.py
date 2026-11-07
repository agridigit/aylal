"""Shared validation envelope: generated Pydantic models -> {valid, errors:[{field, code}]}.

Same verdicts as packages/domain/src/validation (checked against shared vectors).
"""

from typing import Any

from pydantic import BaseModel, ValidationError

from app.domain.phone import normalize_phone
from app.generated.models import (
    ConsentGrant,
    FarmCreate,
    FarmRegistration,
    ParcelCreate,
    PhoneInput,
    ProfileUpdate,
    TrialRecordCreate,
)

RULES: dict[str, type[BaseModel]] = {
    "trial_record.create": TrialRecordCreate,
    "parcel.create": ParcelCreate,
    "farm.create": FarmCreate,
    "phone": PhoneInput,
    "farm": FarmRegistration,
    "consent": ConsentGrant,
    "profile": ProfileUpdate,
}

_TRIMMED_FIELDS = {
    "trial_record.create": ("title",),
    "farm.create": ("name",),
    "farm": ("name",),
    "consent": ("purpose", "text_version"),
    "profile": ("display_name",),
}


def is_valid_polygon(coordinates: list[list[list[float]]]) -> bool:
    if not coordinates:
        return False
    for ring in coordinates:
        if len(ring) < 4 or ring[0] != ring[-1]:
            return False
        if any(len(p) != 2 or abs(p[0]) > 180 or abs(p[1]) > 90 for p in ring):
            return False
    return True


def _code(error_type: str, field: str, loc_len: int, missing: bool) -> str:
    if missing:
        return "required"
    if field == "geometry":
        return "invalid_geometry"
    if error_type in ("literal_error", "enum"):
        return "invalid_choice"
    if field == "area_ha" and error_type == "greater_than_equal":
        return "too_small"
    if error_type == "string_too_short":
        return "too_short"
    if error_type == "string_too_long":
        return "too_long"
    if error_type in ("greater_than_equal", "less_than_equal", "greater_than", "less_than"):
        return "out_of_range"
    return "invalid"


def validate(rule: str, data: Any) -> dict[str, Any]:
    model = RULES[rule]
    payload = data
    if isinstance(data, dict):
        payload = {
            **data,
            **{f: data[f].strip() for f in _TRIMMED_FIELDS.get(rule, ()) if isinstance(data.get(f), str)},
        }

    errors: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def add(field: str, code: str) -> None:
        if (field, code) not in seen:
            seen.add((field, code))
            errors.append({"field": field, "code": code})

    try:
        parsed = model.model_validate(payload)
    except ValidationError as exc:
        for err in exc.errors():
            field = str(err["loc"][0]) if err["loc"] else ""
            add(field, _code(err["type"], field, len(err["loc"]), err["type"] == "missing"))
    else:
        if isinstance(parsed, ParcelCreate) and not is_valid_polygon(parsed.geometry.coordinates):
            add("geometry", "invalid_geometry")
        if isinstance(parsed, PhoneInput) and normalize_phone(parsed.phone) is None:
            add("phone", "invalid")
    return {"valid": not errors, "errors": errors}
