"""Parcel status, mirror of packages/domain/src/parcel-status.ts (shared vectors f3_parcel_status.json)."""
import datetime as dt
from collections.abc import Mapping, Sequence
from typing import Any

PRIORITY = ("weather_alert", "irrigation_need", "health_risk", "vigor_anomaly", "overdue_operations")
RANK = {"ok": 0, "watch": 1, "act": 2}
DOUBT_REASONS = {
    "unknown_threshold": "status.threshold_unvalidated",
    "stale_source": "status.stale_data",
    "imagery_unreliable": "status.imagery_unreliable",
}
NOTHING_TO_DO = "status.nothing_to_do"
_COLOR_ORDER = {"red": 0, "orange": 1, "green": 2}


def _priority(source: str) -> int:
    return PRIORITY.index(source) if source in PRIORITY else len(PRIORITY)


def _live(s: Mapping[str, Any], now: dt.datetime) -> bool:
    observed = dt.datetime.fromisoformat(s["observed_at"])
    return RANK.get(s["severity"], 0) > 0 and observed + dt.timedelta(seconds=s["ttl_s"]) >= now


def parcel_status(signals: Sequence[Mapping[str, Any]], now: dt.datetime, doubts: Sequence[str] = ()) -> dict[str, Any]:
    """Worst severity wins; the reason is the highest-priority signal of that severity; doubt alone is orange."""
    live = sorted(
        (s for s in signals if _live(s, now)), key=lambda s: (-RANK[s["severity"]], _priority(s["source"]))
    )
    items = [
        {"source": s["source"], "severity": s["severity"], "reason_key": s["reason_key"], "observed_at": s["observed_at"]}
        for s in live
    ]
    if live:
        return {"color": "red" if live[0]["severity"] == "act" else "orange", "reason_key": live[0]["reason_key"], "items": items}
    if doubts:
        return {"color": "orange", "reason_key": DOUBT_REASONS.get(doubts[0], "status.doubt"), "items": items}
    return {"color": "green", "reason_key": NOTHING_TO_DO, "items": items}


def sort_parcels(parcels: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """Red, orange, green; ties by contributors (more first) then name."""
    return sorted(parcels, key=lambda p: (_COLOR_ORDER.get(p["color"], 3), -p["contributors"], p["name"]))
