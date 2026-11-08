"""R1-A2/A5: validation of an irrigation system, mirror of irrigation-system-validation.ts."""
from typing import Any


def _err(field: str, code: str) -> dict[str, str]:
    return {"field": field, "code": code, "i18n_key": f"irrigation.system.{field}.{code}"}


def _bad(v: Any) -> bool:
    return v is not None and not (isinstance(v, (int, float)) and v > 0)


def validate_irrigation_system(i: dict[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    for f in ("emitter_flow_lph", "emitter_spacing_m", "row_spacing_m", "pump_flow_m3h", "sectors_count"):
        if _bad(i.get(f)):
            errors.append(_err(f, "must_be_positive"))
    eff = i.get("efficiency")
    if eff is not None and not (0 < eff <= 1):
        errors.append(_err("efficiency", "out_of_range"))
    pump, emitter = i.get("pump_flow_m3h"), i.get("emitter_flow_lph")
    if pump is None and (i.get("kind") != "drip" or emitter is None):
        errors.append(_err("pump_flow_m3h", "flow_required"))
    elif pump is None:
        for f in ("emitter_spacing_m", "row_spacing_m"):
            if i.get(f) is None:
                errors.append(_err(f, "required"))
    return {"valid": not errors, "errors": errors}
