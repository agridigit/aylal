"""Rain input of a past day (G5): the observation when the gateway gave one, else the last known forecast with the source
and the lowered-confidence factor named; neither -> unavailable, never zero. Self-contained (copied into the worker image)."""
from typing import Any


def rain_for_day(*, day: str, observed: dict[str, Any] | None, last_forecast: dict[str, Any] | None) -> dict[str, Any]:
    if observed is not None and observed.get("rain_mm") is not None:
        return {"day": day, "rain_mm": float(observed["rain_mm"]), "rain_source": "observed", "confidence_factor": None, "availability": "ok"}
    if last_forecast is not None and last_forecast.get("rain_mm") is not None:
        return {"day": day, "rain_mm": float(last_forecast["rain_mm"]), "rain_source": "forecast", "confidence_factor": "rain_not_observed", "availability": "ok"}
    return {"day": day, "rain_mm": None, "rain_source": None, "confidence_factor": None, "availability": "unavailable"}
