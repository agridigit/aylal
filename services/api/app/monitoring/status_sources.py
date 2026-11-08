"""Registry of status sources (FR-013): a source not delivered contributes nothing, without error. Mirror of status-sources.ts."""
import logging
from collections.abc import Callable, Iterable, Mapping
from typing import Any

SourceReader = Callable[[], list[dict[str, Any]] | str]
_TABLE_OF = {"irrigation_need": "irrigation_plans", "health_risk": "health_diagnoses", "overdue_operations": "operation_parcels"}
_ALWAYS = ("weather_alert", "vigor_anomaly")
_LOG = logging.getLogger(__name__)


def collect_signals(registry: Mapping[str, SourceReader | None]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for name, read in registry.items():
        if read is None:
            continue
        try:
            signals = read()
        except Exception:  # noqa: BLE001 - a failing source must never break the status of the others
            _LOG.warning("status source %s failed", name)
            continue
        if isinstance(signals, list):
            out.extend(signals)
    return out


def available_sources(tables: Iterable[str]) -> set[str]:
    """F3 sources always exist; F4/F5/F6 sources exist only when their tables do."""
    present = set(tables)
    return {*_ALWAYS, *(s for s, t in _TABLE_OF.items() if t in present)}


def drop_unreliable_vigor(signals: Iterable[dict[str, Any]], reliability: str) -> list[dict[str, Any]]:
    """Unreliable imagery (small parcel, greenhouse) never drives the status."""
    return [s for s in signals if not (reliability == "low" and s["source"] == "vigor_anomaly")]
