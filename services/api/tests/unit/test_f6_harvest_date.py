"""T054 - earliest harvest date mirrors packages/domain/src/harvest-date.ts (shared vector f6_harvest_date.json)."""
import datetime as dt
import json
import os
from pathlib import Path

import pytest

DOMAIN_DIR = Path(os.environ.get("AYLAL_DOMAIN_DIR", "/packages/domain"))
VECTOR = json.loads((DOMAIN_DIR / "vectors" / "f6_harvest_date.json").read_text(encoding="utf-8"))
TODAY = dt.date.fromisoformat(VECTOR["today"])


@pytest.mark.parametrize("case", VECTOR["cases"], ids=lambda c: c["name"])
def test_given_registry_entries_when_computing_then_the_result_matches_the_vector(case):
    from app.domain.harvest_date import earliest_harvest

    assert earliest_harvest(case["entries"], TODAY) == case["expected"]


def test_given_entries_in_any_order_when_computing_then_the_result_is_the_same():
    from app.domain.harvest_date import earliest_harvest

    case = VECTOR["cases"][1]
    assert earliest_harvest(list(reversed(case["entries"])), TODAY) == case["expected"]
