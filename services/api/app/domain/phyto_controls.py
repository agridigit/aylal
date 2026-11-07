"""Phyto treatment controls, mirror of packages/domain/src/phyto-controls.ts. Warnings never block a save."""
from typing import Any

from app.domain.units import convert_dose

WARNING_CODES = (
    "not_authorized_for_crop", "dose_above_max", "max_applications_reached", "dar_unknown", "free_product_unchecked",
)


def phyto_warnings(data: dict[str, Any]) -> list[str]:
    """Warning codes of one treatment on one parcel, in a stable order."""
    if not data.get("product_id"):
        return ["free_product_unchecked"] if data.get("free_product_name") else []
    crop = data.get("crop_slug")
    use = next((u for u in data.get("uses") or [] if crop and u["crop_slug"] == crop), None)
    if use is None:
        return ["not_authorized_for_crop"]
    out: list[str] = []
    dose, unit = data.get("dose"), data.get("dose_unit")
    if dose is not None and unit and use.get("max_dose") is not None and use.get("dose_unit"):
        converted = convert_dose(dose, unit, use["dose_unit"])
        if converted is not None and float(converted) > float(use["max_dose"]) + 1e-9:
            out.append("dose_above_max")
    maximum = use.get("max_applications")
    if maximum is not None and data.get("applications_so_far", 0) >= maximum:
        out.append("max_applications_reached")
    if use.get("dar_days") is None:
        out.append("dar_unknown")
    return out


def phyto_warnings_by_parcel(base: dict[str, Any], parcels: list[dict[str, Any]]) -> dict[str, list[str]]:
    """The same controls applied parcel by parcel (each parcel has its own crop and application count)."""
    return {
        p["id"]: phyto_warnings({**base, "crop_slug": p.get("crop_slug"), "applications_so_far": p.get("applications_so_far", 0)})
        for p in parcels
    }
