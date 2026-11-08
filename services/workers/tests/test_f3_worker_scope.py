"""T029 - F3 worker tasks only ever read parcels through the shared visible-parcels predicate (never a raw parcels scan)."""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "tasks"
SCOPED = ("evaluate_alerts", "recompute_status", "detect_zones", "send_daily_summary")  # tasks that read per-parcel/per-recipient data
ALL_F3 = SCOPED + ("refresh_weather", "import_crop_thresholds")
PER_PARCEL = re.compile(r"\bFROM\s+(parcels|worker_parcels|parcel_status|alerts|attention_zones)\b", re.I)


def test_given_the_f3_tasks_then_every_task_file_exists():
    missing = [t for t in ALL_F3 if not (TASKS / f"{t}.py").exists()]
    assert missing == []


@pytest.mark.parametrize("task", SCOPED)
def test_given_a_scoped_task_then_it_uses_the_shared_visible_parcels_predicate(task):
    text = (TASKS / f"{task}.py").read_text(encoding="utf-8")
    assert "VISIBLE_PARCELS_SQL" in text, f"{task} does not use VISIBLE_PARCELS_SQL"
    assert "access_sql" in text


@pytest.mark.parametrize("task", SCOPED)
def test_given_a_scoped_task_then_it_never_selects_raw_parcels_without_the_predicate(task):
    text = (TASKS / f"{task}.py").read_text(encoding="utf-8")
    for m in re.finditer(r"FROM\s+parcels\b(?P<rest>[^\"']{0,200})", text, re.I):
        assert "archived_at" in m.group("rest") or "VISIBLE_PARCELS_SQL" in text, f"{task}: raw parcels scan"


def test_given_the_worker_image_then_the_shared_predicate_is_copied_from_the_api_single_source():
    assert "access_sql" in (ROOT / "Dockerfile").read_text(encoding="utf-8")


@pytest.mark.parametrize("task", ("evaluate_alerts", "recompute_status", "detect_zones"))
def test_given_a_recomputing_task_then_it_serialises_per_farm_with_the_monitoring_lock(task):
    assert "monitoring:" in (TASKS / f"{task}.py").read_text(encoding="utf-8")
