"""T065 - Python mirror of planSeasonStart: rotation, intercropping, one active season per crop (R6-A1 to R6-A3)."""
import json
import os
from pathlib import Path

import pytest

DOMAIN_DIR = Path(os.environ.get("AYLAL_DOMAIN_DIR", "/packages/domain"))
VECTORS = json.loads((DOMAIN_DIR / "vectors" / "f2_season_rotation.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("v", VECTORS, ids=lambda v: v["name"])
def test_given_the_active_seasons_when_planning_a_start_then_python_matches_the_shared_vector(v):
    from app.domain.season_rules import plan_season_start

    r = plan_season_start(v["active"], v["cropId"], v["closeIds"])
    assert r["ok"] is v["expected"]["ok"]
    if v["expected"]["ok"]:
        assert sorted(r["closeIds"]) == v["expected"]["closeIds"]
    else:
        assert r["code"] == v["expected"]["code"]
