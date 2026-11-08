"""R5-A4: age and assumptions of a water analysis, mirror of water-analysis.ts."""
import datetime as dt
from typing import Any


def analysis_age_days(i: dict[str, Any]) -> dict[str, Any]:
    age = (dt.date.fromisoformat(i["today"]) - dt.date.fromisoformat(i["analysed_on"])).days
    return {"age_days": None, "error": "in_the_future"} if age < 0 else {"age_days": age}


def analysis_assumptions(i: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = [{"key": "ece_ds_m", "value": i["ec_ds_m"]}]
    if i.get("water_source"):
        out.append({"key": "water_source", "value": i["water_source"]})
    age = analysis_age_days(i)["age_days"]
    if age is not None:
        out.append({"key": "analysis_age_days", "value": age})
    if i.get("leaching_fraction") is not None:
        out.append({"key": "leaching_fraction", "value": i["leaching_fraction"]})
    elif i.get("unavailable_reason"):
        out.append({"key": "leaching_unavailable_reason", "value": i["unavailable_reason"]})
    return out


def is_old_analysis(i: dict[str, Any]) -> dict[str, bool]:
    limit = i.get("max_age_days")
    return {"old": limit is not None and i["age_days"] > limit}
