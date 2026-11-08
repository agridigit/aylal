"""T013 - G5: empty referentials -> `unavailable` with a reason, never a default value; no agronomic literal in the domain."""
import re
from pathlib import Path

import pytest

from tests.unit._f4 import run, vector_params

APP = Path(__file__).resolve().parents[2] / "app"
REPO = Path("/repo")


@pytest.mark.parametrize("v", vector_params("f4_reference_gaps.json"))
def test_given_a_referential_gap_when_resolving_then_unavailable_with_a_reason_and_no_default(v):
    run(v, "app.domain.irrigation_advice")


def test_given_the_domain_and_irrigation_sources_then_no_kc_root_depth_or_soil_reserve_literal_exists():
    files = sorted((APP / "domain").glob("*.py")) + sorted((APP / "irrigation").glob("*.py"))
    targets = [p for p in files if re.search(r"irrigation|water|et0|leaching|advice|application|rainfed|effective|reference|weather_input", p.name)]
    assert any(p.name == "irrigation_advice.py" for p in targets), "irrigation_advice.py missing"
    bad = re.compile(r"\b(kc|root_?depth\w*|taw\w*|available_water\w*|reserve\w*|soil\w*)\s*[:=]\s*-?\d+(\.\d+)?", re.I)
    for p in targets:
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith(("#", '"""')):
                continue
            assert not bad.search(line), f"{p.name}:{i} {line.strip()}"


def test_given_the_f4_migration_then_it_inserts_no_agronomic_row():
    found = sorted((APP.parent / "alembic" / "versions").glob("*_irrigation_water_balance.py"))
    assert found, "irrigation_water_balance migration missing"
    text = found[0].read_text(encoding="utf-8")
    for table in ("crop_irrigation_params", "soil_textures", "irrigation_params"):
        assert not re.search(rf"INSERT\s+INTO\s+{table}", text, re.I), table
        assert not re.search(rf"bulk_insert\(\s*[\w.]*{table}", text), table
