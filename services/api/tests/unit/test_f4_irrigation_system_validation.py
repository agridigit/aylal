"""T047 (US1) - validation and defaults of an irrigation system. Python mirror of packages/domain/tests/irrigation-system-us1.test.ts.
The validator module does not exist yet: it is imported inside each test (the failure is the missing feature)."""
import pytest

from app.domain.application_rate import application_rate
from app.domain.irrigation_efficiency import resolve_efficiency

PUMP = {"kind": "drip", "sectors_count": 2, "pump_flow_m3h": 10}
EMITTERS = {"kind": "drip", "sectors_count": 2, "emitter_flow_lph": 4, "emitter_spacing_m": 0.5, "row_spacing_m": 2}


def _validate(payload):
    from app.domain.irrigation_system_validation import validate_irrigation_system

    return validate_irrigation_system(payload)


def test_given_a_system_described_by_the_pump_flow_then_it_is_accepted_without_emitter_flow_or_spacings():
    assert _validate(PUMP) == {"valid": True, "errors": []}


def test_given_a_drip_system_with_emitters_and_spacings_then_it_is_accepted():
    assert _validate(EMITTERS)["valid"] is True


@pytest.mark.parametrize("field,patch", [
    ("emitter_flow_lph", {**EMITTERS, "emitter_flow_lph": 0}),
    ("emitter_flow_lph", {**EMITTERS, "emitter_flow_lph": -3}),
    ("emitter_spacing_m", {**EMITTERS, "emitter_spacing_m": 0}),
    ("row_spacing_m", {**EMITTERS, "row_spacing_m": 0}),
    ("pump_flow_m3h", {**PUMP, "pump_flow_m3h": 0}),
    ("sectors_count", {**PUMP, "sectors_count": 0}),
    ("efficiency", {**PUMP, "efficiency": 0}),
])
def test_given_an_incoherent_value_then_the_field_is_named_with_an_i18n_key(field, patch):
    out = _validate(patch)
    assert out["valid"] is False
    first = out["errors"][0]
    assert first["field"] == field and first["i18n_key"].startswith("irrigation.") and first["code"]


def test_given_a_system_without_any_flow_then_it_is_refused_on_the_flow_and_no_rate_is_invented():
    out = _validate({"kind": "sprinkler", "sectors_count": 1})
    assert out["valid"] is False and "flow_required" in [e["code"] for e in out["errors"]]


@pytest.mark.parametrize("kind,expected", [("drip", 0.9), ("sprinkler", 0.75), ("pivot", 0.75), ("gravity", 0.6)])
def test_given_a_type_without_efficiency_then_the_default_of_the_type_applies_and_is_visible(kind, expected):
    assert resolve_efficiency({"kind": kind, "efficiency": None}) == {"efficiency": expected, "is_default": True}


def test_given_emitters_then_the_rate_per_m2_is_flow_over_spacings():
    assert abs(application_rate({**EMITTERS, "pump_flow_m3h": None, "area_m2": None})["rate_mm_h"] - 4.0) < 1e-6


def test_given_a_pump_flow_then_the_rate_uses_equal_sector_surfaces():
    out = application_rate({**PUMP, "emitter_flow_lph": None, "emitter_spacing_m": None, "row_spacing_m": None, "sectors_count": 4, "area_m2": 40000})
    assert abs(out["rate_mm_h"] - 10000 / 10000) < 1e-6  # 10 m3/h over 10 000 m2 per sector = 1 mm/h
