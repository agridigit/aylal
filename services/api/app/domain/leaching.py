"""FAO-29 leaching requirement and gross need, mirror of leaching.ts."""
from typing import Any


def leaching_fraction(i: dict[str, Any]) -> dict[str, Any]:
    emax, lmax = i.get("ece_max_ds_m"), i.get("leaching_max")
    if not isinstance(emax, (int, float)) or not isinstance(lmax, (int, float)):
        return {"leaching_fraction": None, "unavailable_reason": "no_salinity_reference"}
    thr = i.get("ece_threshold_ds_m")
    if isinstance(thr, (int, float)) and i["ecw_ds_m"] <= thr:
        return {"leaching_fraction": 0}
    den = 5 * emax - i["ecw_ds_m"]
    if den <= 0:
        return {"leaching_fraction": lmax}
    return {"leaching_fraction": min(lmax, i["ecw_ds_m"] / den)}


def gross_need(i: dict[str, Any]) -> dict[str, Any]:
    return {"gross_need_mm": i["net_need_mm"] / (1 - i["leaching_fraction"])}
