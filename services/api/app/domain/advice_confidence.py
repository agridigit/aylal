"""Advice confidence (product rule), mirror of advice-confidence.ts."""
from typing import Any


def advice_confidence(i: dict[str, Any]) -> dict[str, Any]:
    f: list[str] = []
    if i["stale"]:
        f.append("stale_data")
    if not i["validated"]:
        f.append("not_validated")
    if i.get("et0_method") == "hargreaves":
        f.append("et0_estimated")
    if i.get("rain_source") not in (None, "observed", "ignored_greenhouse"):
        f.append("rain_not_observed")
    if i["soil_default"]:
        f.append("soil_default")
    if i["efficiency_is_default"]:
        f.append("efficiency_default")
    if i["analysis_old"]:
        f.append("analysis_old")
    if i["initial_state_assumed"]:
        f.append("initial_state_assumed")
    level = "low" if i["stale"] or len(f) >= 3 else "medium" if f else "high"
    return {"confidence": level, "factors": f}
