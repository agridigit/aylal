"""T068 - R5-A2, R5-A4: sources are combined; an unavailable source (F4, F5) is ignored without error; unreliable imagery does not drive the status."""
import json
import os
from pathlib import Path

import pytest

from app.domain.parcel_status import parcel_status
from app.monitoring.status_sources import available_sources, collect_signals, drop_unreliable_vigor

DOMAIN_DIR = Path(os.environ.get("AYLAL_DOMAIN_DIR", "/packages/domain"))
V = json.loads((DOMAIN_DIR / "vectors/f3_parcel_status.json").read_text(encoding="utf-8"))


def _sig(source, severity="watch"):
    return {"source": source, "severity": severity, "reason_key": f"status.{source}", "observed_at": "2026-12-05T08:00:00+00:00", "ttl_s": 86400}


def test_given_sources_when_collecting_then_every_available_source_contributes():
    got = collect_signals({"weather_alert": lambda: [_sig("weather_alert", "act")], "overdue_operations": lambda: [_sig("overdue_operations")]})
    assert {s["source"] for s in got} == {"weather_alert", "overdue_operations"}


def test_given_a_source_not_delivered_when_collecting_then_it_is_ignored_without_error():
    got = collect_signals({"weather_alert": lambda: [_sig("weather_alert")], "irrigation_need": None, "health_risk": None})
    assert [s["source"] for s in got] == ["weather_alert"]


def test_given_a_source_reporting_unavailable_when_collecting_then_it_is_ignored_without_error():
    assert collect_signals({"irrigation_need": lambda: "unavailable"}) == []


def test_given_a_source_that_raises_when_collecting_then_the_other_sources_still_count():
    def boom():
        raise RuntimeError("source down")

    got = collect_signals({"health_risk": boom, "weather_alert": lambda: [_sig("weather_alert", "act")]})
    assert [s["source"] for s in got] == ["weather_alert"]


def test_given_the_present_tables_when_listing_sources_then_f6_is_available_and_f4_f5_only_if_their_tables_exist():
    assert available_sources({"operation_parcels"}) == {"weather_alert", "vigor_anomaly", "overdue_operations"}
    assert "irrigation_need" not in available_sources({"operation_parcels"})
    assert "health_risk" not in available_sources({"operation_parcels"})


def test_given_unreliable_imagery_when_filtering_then_the_vigor_signal_does_not_drive_the_status():
    sigs = [_sig("vigor_anomaly", "act"), _sig("weather_alert", "watch")]
    assert [s["source"] for s in drop_unreliable_vigor(sigs, "low")] == ["weather_alert"]
    assert len(drop_unreliable_vigor(sigs, "ok")) == 2


def test_given_the_vectors_when_combining_collected_signals_then_the_status_matches():
    for c in V["cases"]:
        got = parcel_status(c["signals"], __import__("datetime").datetime.fromisoformat(c["now"].replace("Z", "+00:00")), c["doubts"])
        assert got["color"] == c["expected"]["color"], c["name"]


@pytest.mark.parametrize("available", [set(), {"weather_alert"}])
def test_given_no_signal_at_all_when_collecting_then_the_parcel_is_green_nothing_to_do(available):
    registry = dict.fromkeys(available, list)
    out = parcel_status(collect_signals(registry), __import__("datetime").datetime(2026, 12, 5, 9, tzinfo=__import__("datetime").UTC), [])
    assert out["color"] == "green" and out["reason_key"] == "status.nothing_to_do"
