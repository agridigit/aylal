"""Earliest harvest date, mirror of packages/domain/src/harvest-date.ts."""
import datetime as dt
from typing import Any


def earliest_harvest(entries: list[dict[str, Any]], today: dt.date) -> dict[str, Any]:
    """Longest pre-harvest interval among live (not reversed) applications."""
    reversed_ids = {e["supersedes_id"] for e in entries if e["entry_kind"] == "reversal" and e.get("supersedes_id")}
    date: dt.date | None = None
    limiting: str | None = None
    unknown = False
    for e in entries:
        if e["entry_kind"] != "application" or e["id"] in reversed_ids:
            continue
        if e.get("dar_days") is None:
            unknown = True
            continue
        performed = e["performed_on"]
        performed = performed if isinstance(performed, dt.date) else dt.date.fromisoformat(performed)
        end = performed + dt.timedelta(days=e["dar_days"])
        if date is None or end > date:
            date, limiting = end, e.get("product_name")
    return {
        "date": date.isoformat() if date else None,
        "harvestable_now": date is None or date <= today,
        "unknown_dar": unknown,
        "limiting_product": limiting,
    }
