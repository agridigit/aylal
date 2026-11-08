"""Per crop and stage weather thresholds (reference data validated by agronomy; tests use fixtures only)."""
from collections.abc import Iterable, Mapping
from typing import Any


def thresholds_for(rows: Iterable[Mapping[str, Any]], crop_slug: str, stage_key: str) -> Mapping[str, Any] | None:
    """The row for the pair, or None: an unknown pair never gets a default value."""
    for row in rows:
        if row["crop_slug"] == crop_slug and row["stage_key"] == stage_key:
            return row
    return None
