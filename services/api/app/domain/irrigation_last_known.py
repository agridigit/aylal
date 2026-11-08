"""R2-A6: the advice to serve, mirror of irrigation-last-known.ts."""
from typing import Any


def select_served_plan(i: dict[str, Any]) -> dict[str, Any]:
    past = [p for p in i["plans"] if p["for_date"] <= i["today"]]
    valid = max((p for p in past if p["kind"] != "unavailable"), key=lambda p: p["for_date"], default=None)
    if valid is not None:
        last = valid["for_date"] < i["today"]
        return {"served": valid, "is_last_known": last, "confidence": "low" if last else valid["confidence"]}
    latest = max(past, key=lambda p: p["for_date"], default=None)
    return {"served": latest, "is_last_known": False, "confidence": "low"}
