"""Worker-safe view of an advice (decisions point 19), mirror of advice-worker-view.ts. Deny-by-default whitelists."""
import copy
from typing import Any

WORKER_ASSUMPTION_KEYS = ("et0", "kc", "effective_rain", "efficiency", "application_rate", "rain_source")
WORKER_ADVICE_KEYS = (
    "parcel_id", "for_date", "kind", "total_minutes", "sectors", "net_need_mm", "stress_level", "confidence",
    "assumptions", "unavailable_reason", "computed_at", "is_last_known", "ready_before_7",
)
STAFF_ROLES = frozenset({"owner", "manager"})


def worker_assumptions(i: dict[str, Any]) -> dict[str, Any]:
    return {"assumptions": [copy.deepcopy(a) for a in i["assumptions"] if a.get("key") in WORKER_ASSUMPTION_KEYS]}


def advice_view(i: dict[str, Any]) -> dict[str, Any]:
    advice: dict[str, Any] = copy.deepcopy(i["advice"])
    if i["role"] in STAFF_ROLES:
        return advice
    out = {k: advice[k] for k in WORKER_ADVICE_KEYS if k in advice}
    if isinstance(out.get("assumptions"), list):
        out["assumptions"] = worker_assumptions({"assumptions": out["assumptions"]})["assumptions"]
    return out
