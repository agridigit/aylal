"""Default efficiencies (CPS section 9), mirror of irrigation-efficiency.ts."""
from typing import Any

_DEFAULTS = {"drip": 0.9, "sprinkler": 0.75, "pivot": 0.75, "gravity": 0.6}


def resolve_efficiency(i: dict[str, Any]) -> dict[str, Any]:
    if i.get("efficiency") is not None:
        return {"efficiency": i["efficiency"], "is_default": False}
    return {"efficiency": _DEFAULTS.get(i["kind"]), "is_default": True}
