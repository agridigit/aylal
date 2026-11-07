"""T009 - Python mirrors of the F2 domain rules give the same verdicts as TS on the shared vectors."""
import json
import os
from pathlib import Path

import pytest

DOMAIN_DIR = Path(os.environ.get("AYLAL_DOMAIN_DIR", "/packages/domain"))


def _load(name: str) -> list[dict]:
    return json.loads((DOMAIN_DIR / "vectors" / name).read_text(encoding="utf-8"))


def _polygon(n: int, lon=-7.6, lat=33.57, r=0.01):
    import math

    return [[lon + r * math.cos(2 * math.pi * i / n), lat + r * math.sin(2 * math.pi * i / n)] for i in range(n)]


@pytest.mark.parametrize("v", _load("f2_area.json"), ids=lambda v: v["name"])
def test_given_a_ring_when_computing_the_area_then_it_is_within_half_a_percent_of_the_shared_vector(v):
    from app.domain.geometry import area_ha

    assert abs(area_ha(v["ring"]) - v["expectedHa"]) / v["expectedHa"] < 0.005


@pytest.mark.parametrize("v", _load("f2_self_intersection.json"), ids=lambda v: v["name"])
def test_given_a_ring_when_validating_then_python_matches_the_ts_verdict(v):
    from app.domain.geometry import validate_ring

    r = validate_ring(v["ring"])
    assert r["ok"] is v["expected"]["ok"]
    if not v["expected"]["ok"]:
        assert r["code"] == v["expected"]["code"]
        if "crossings" in v["expected"]:
            assert len(r["crossings"]) == v["expected"]["crossings"]


def test_given_500_and_501_vertices_when_validating_then_the_bound_is_500():
    from app.domain.geometry import validate_ring

    assert validate_ring(_polygon(500))["ok"] is True
    r = validate_ring(_polygon(501))
    assert (r["ok"], r["code"]) == (False, "too_many_vertices")


@pytest.mark.parametrize("v", _load("f2_overlap.json"), ids=lambda v: v["name"])
def test_given_other_fields_when_checking_overlaps_then_python_matches_the_ts_ids(v):
    from app.domain.geometry import overlap_warnings

    assert sorted(overlap_warnings(v["ring"], v["others"])) == v["expected"]


@pytest.mark.parametrize("v", _load("f2_season_rules.json"), ids=lambda v: f"{v['fn']}:{v['name']}")
def test_given_season_input_when_applying_the_rule_then_python_matches_the_ts_verdict(v):
    from app.domain.season_rules import can_start_season, season_date

    if v["fn"] == "canStartSeason":
        assert can_start_season(v["active"], v["cropId"]) == v["expected"]
    else:
        r = season_date({"cycle": v["cycle"]}, v["input"], v["today"])
        assert r["ok"] is v["expected"]["ok"]
        if not v["expected"]["ok"]:
            assert r["code"] == v["expected"]["code"]


@pytest.mark.parametrize("v", _load("f2_merge.json"), ids=lambda v: v["name"])
def test_given_fields_to_merge_when_merging_then_python_matches_the_ts_result(v):
    from app.domain.field_rules import merge_fields

    r = merge_fields(v["survivor"], v["others"], v["seasons"])
    assert r["ok"] is v["expected"]["ok"]
    if not v["expected"]["ok"]:
        assert r["code"] == v["expected"]["code"]
        return
    assert abs(r["area_ha"] - v["expected"]["areaHa"]) / v["expected"]["areaHa"] < 0.005
    assert sorted(r["kept_season_ids"]) == v["expected"]["keptSeasonIds"]
    assert sorted(r["dropped_season_ids"]) == v["expected"]["droppedSeasonIds"]


def test_given_the_field_limits_then_they_match_the_spec():
    from app.domain.field_rules import LIMITS, can_create_field, imagery_suitable

    assert LIMITS == {
        "MIN_VERTICES": 3, "MAX_VERTICES": 500, "MAX_AREA_HA": 5000,
        "MAX_FIELDS_PER_FARM": 500, "MAX_NAME_LENGTH": 80,
    }
    assert can_create_field(499) == {"ok": True}
    assert can_create_field(500) == {"ok": False, "code": "field_limit_reached"}
    assert imagery_suitable(0.3, False) is True and imagery_suitable(0.29, False) is False
    assert imagery_suitable(5, True) is False


def test_given_a_field_input_when_validating_then_name_area_and_extent_rules_apply():
    from app.domain.field_rules import validate_field

    ring = [[-7.6, 33.57], [-7.599, 33.57], [-7.599, 33.571], [-7.6, 33.571], [-7.6, 33.57]]
    assert validate_field({"name": "Haouz", "ring": ring})["ok"] is True
    assert validate_field({"name": "a" * 81, "ring": ring})["code"] == "name_invalid"
    assert validate_field({"name": "  ", "ring": ring})["code"] == "name_invalid"
    paris = [[2.35, 48.85], [2.351, 48.85], [2.351, 48.851], [2.35, 48.851], [2.35, 48.85]]
    assert validate_field({"name": "P", "ring": paris})["code"] == "outside_morocco"
    huge = [[-7.6, 33.0], [-7.1, 33.0], [-7.1, 33.5], [-7.6, 33.5], [-7.6, 33.0]]
    assert validate_field({"name": "H", "ring": huge})["code"] == "area_too_large"


def test_given_a_stage_estimate_then_days_are_approximate_and_corrected_stage_wins():
    from app.domain.season_rules import display_stage, estimate_stage

    crop = {"cycle": "annual", "stages": [
        {"key": "emergence", "gdd_from": 0, "label_key": "a"}, {"key": "tillering", "gdd_from": 100, "label_key": "b"},
        {"key": "heading", "gdd_from": 400, "label_key": "c"}]}
    assert estimate_stage(crop, {"sowing_date": "2026-01-01"}, "2026-05-01") == {"stage": "tillering", "approximate": True}
    assert estimate_stage(crop, {"sowing_date": "2026-01-01"}, "2026-02-01", 450) == {"stage": "heading", "approximate": False}
    assert display_stage({"stage_estimated": "tillering", "stage_corrected": "heading"}) == "heading"
