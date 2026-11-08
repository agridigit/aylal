"""T054 - R3-A2, R3-A3: the 80 percent clear-sky rule, zonal statistics computed locally, and the low-reliability flag."""
import json
import os
from pathlib import Path

import numpy as np
import pytest

from app.domain.imagery_reliability import imagery_reliability
from app.domain.vigor import is_scene_publishable
from app.monitoring.imagery import zonal_stats

DOMAIN_DIR = Path(os.environ.get("AYLAL_DOMAIN_DIR", "/packages/domain"))
CASES = json.loads((DOMAIN_DIR / "vectors/f3_cloud_rule.json").read_text(encoding="utf-8"))
RELIABILITY = json.loads((DOMAIN_DIR / "vectors/f3_reliability.json").read_text(encoding="utf-8"))
SCL_VEGETATION, SCL_BARE, SCL_CLOUD_MEDIUM, SCL_CLOUD_SHADOW, SCL_SNOW = 4, 5, 8, 3, 11


@pytest.mark.parametrize("c", CASES, ids=lambda c: str(c["clear_pct"]))
def test_given_a_clear_percentage_then_publication_follows_the_vectors(c):
    assert is_scene_publishable(c["clear_pct"]) is c["publishable"]


@pytest.mark.parametrize("c", RELIABILITY, ids=lambda c: f"{c['area_ha']}-{c['greenhouse']}")
def test_given_a_parcel_then_reliability_follows_the_vectors(c):
    assert imagery_reliability(c["area_ha"], c["greenhouse"], 0.3) == c["reliability"]


def _bands(n=10, red=0.1, nir=0.5, swir=0.3):
    full = lambda v: np.full((n, n), v, dtype="float64")  # noqa: E731
    return full(red), full(nir), full(swir), np.full((n, n), SCL_VEGETATION, dtype="uint8")


def test_given_clear_pixels_when_computing_then_vigor_and_plant_moisture_follow_the_band_formulas():
    b04, b08, b11, scl = _bands()
    s = zonal_stats(b04=b04, b08=b08, b11=b11, scl=scl, mask=np.ones((10, 10), dtype=bool))
    assert s["vigor_mean"] == pytest.approx((0.5 - 0.1) / (0.5 + 0.1))
    assert s["plant_moisture_mean"] == pytest.approx((0.5 - 0.3) / (0.5 + 0.3))
    assert s["clear_pct"] == pytest.approx(100.0)


def test_given_25_percent_cloud_over_the_parcel_when_computing_then_clear_pct_is_75_and_the_scene_is_not_publishable():
    b04, b08, b11, scl = _bands()
    scl[:5, :5] = SCL_CLOUD_MEDIUM
    s = zonal_stats(b04=b04, b08=b08, b11=b11, scl=scl, mask=np.ones((10, 10), dtype=bool))
    assert s["clear_pct"] == pytest.approx(75.0)
    assert is_scene_publishable(s["clear_pct"]) is False


def test_given_shadow_and_snow_when_computing_then_they_count_as_not_clear():
    b04, b08, b11, scl = _bands()
    scl[0, :] = SCL_CLOUD_SHADOW
    scl[1, :] = SCL_SNOW
    s = zonal_stats(b04=b04, b08=b08, b11=b11, scl=scl, mask=np.ones((10, 10), dtype=bool))
    assert s["clear_pct"] == pytest.approx(80.0)


def test_given_a_parcel_mask_when_computing_then_pixels_outside_the_parcel_are_ignored():
    b04, b08, b11, scl = _bands()
    scl[5:, :] = SCL_CLOUD_MEDIUM  # outside the parcel
    mask = np.zeros((10, 10), dtype=bool)
    mask[:5, :] = True
    assert zonal_stats(b04=b04, b08=b08, b11=b11, scl=scl, mask=mask)["clear_pct"] == pytest.approx(100.0)


def test_given_cloudy_pixels_when_computing_then_the_means_use_clear_pixels_only():
    b04, b08, b11, scl = _bands()
    b08[:5, :] = 0.9  # cloud pixels would lift the mean if they were used
    scl[:5, :] = SCL_CLOUD_MEDIUM
    s = zonal_stats(b04=b04, b08=b08, b11=b11, scl=scl, mask=np.ones((10, 10), dtype=bool))
    assert s["vigor_mean"] == pytest.approx((0.5 - 0.1) / (0.5 + 0.1))


def test_given_an_empty_mask_when_computing_then_no_value_is_invented():
    b04, b08, b11, scl = _bands()
    s = zonal_stats(b04=b04, b08=b08, b11=b11, scl=scl, mask=np.zeros((10, 10), dtype=bool))
    assert s["clear_pct"] == 0.0 and s["vigor_mean"] is None and s["plant_moisture_mean"] is None


def test_given_zero_reflectance_pixels_when_computing_then_there_is_no_division_error():
    z = np.zeros((4, 4))
    s = zonal_stats(b04=z, b08=z, b11=z, scl=np.full((4, 4), SCL_VEGETATION, dtype="uint8"), mask=np.ones((4, 4), dtype=bool))
    assert s["vigor_mean"] is None or np.isfinite(s["vigor_mean"])
