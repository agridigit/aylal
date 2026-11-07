"""T042 - phyto controls mirror packages/domain/src/phyto-controls.ts (shared vector f6_phyto_controls.json)."""
import json
import os
from pathlib import Path

import pytest

DOMAIN_DIR = Path(os.environ.get("AYLAL_DOMAIN_DIR", "/packages/domain"))
VECTOR = json.loads((DOMAIN_DIR / "vectors" / "f6_phyto_controls.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", VECTOR["cases"], ids=lambda c: c["name"])
def test_given_a_treatment_when_checking_then_the_warnings_match_the_vector(case):
    from app.domain.phyto_controls import phyto_warnings

    assert phyto_warnings(case["input"]) == case["expected"]


@pytest.mark.parametrize("case", VECTOR["by_parcel"], ids=lambda c: c["name"])
def test_given_parcels_of_different_crops_when_checking_then_each_parcel_gets_its_own_warnings(case):
    from app.domain.phyto_controls import phyto_warnings_by_parcel

    assert phyto_warnings_by_parcel(case["base"], case["parcels"]) == case["expected"]


def test_given_any_vector_input_when_checking_then_it_never_raises_and_returns_known_codes():
    from app.domain.phyto_controls import WARNING_CODES, phyto_warnings

    for case in VECTOR["cases"]:
        assert set(phyto_warnings(case["input"])) <= set(WARNING_CODES)
    assert set(WARNING_CODES) == {
        "not_authorized_for_crop", "dose_above_max", "max_applications_reached", "dar_unknown", "free_product_unchecked",
    }
