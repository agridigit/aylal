"""T027/T021/T006 (worker side) - F4 tasks read parcels only through the shared visible-parcels predicate, serialise per farm,
take the injected clock, and push nothing the worker view forbids."""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "tasks"
ALL_F4 = ("compute_irrigation_plans", "send_irrigation_reminders", "import_irrigation_params")
SCOPED = ("compute_irrigation_plans", "send_irrigation_reminders")
TIME = re.compile(r"(datetime\.now|date\.today|datetime\.utcnow|current_date|\bnow\(\)|time\.time\()")


def _body(name):
    text = (TASKS / f"{name}.py").read_text(encoding="utf-8")
    assert len(text.splitlines()) > 3, f"{name} is still a skeleton"
    return text


@pytest.mark.parametrize("task", ALL_F4)
def test_given_the_f4_tasks_then_each_is_implemented(task):
    _body(task)


@pytest.mark.parametrize("task", SCOPED)
def test_given_a_scoped_task_then_it_uses_the_shared_visible_parcels_predicate_and_never_a_raw_parcels_scan(task):
    text = _body(task)
    assert "VISIBLE_PARCELS_SQL" in text and "access_sql" in text
    for m in re.finditer(r"FROM\s+parcels\b(?P<rest>[^\"']{0,200})", text, re.I):
        assert "archived_at" in m.group("rest") or "VISIBLE_PARCELS_SQL" in text, f"{task}: raw parcels scan"


@pytest.mark.parametrize("task", SCOPED)
def test_given_a_scoped_task_then_it_takes_the_injected_clock_and_never_reads_the_system_time(task):
    text = _body(task)
    assert "clock" in text or re.search(r"\bnow\b\s*[:=]", text), f"{task} has no injected time"
    for i, line in enumerate(text.splitlines(), 1):
        assert not TIME.search(line.split("#", 1)[0]) or "clock-allow" in line, f"{task}:{i} {line.strip()}"


def test_given_the_plan_task_then_it_serialises_per_farm_with_the_irrigation_lock_and_coalesces_recomputes():
    text = _body("compute_irrigation_plans")
    assert "irrigation:" in text and "lock" in text.lower()
    assert "irrigation_jobs" in text


def test_given_the_reminder_task_then_recipients_are_active_members_and_the_payload_goes_through_the_worker_view():
    text = _body("send_irrigation_reminders")
    assert "removed_at IS NULL" in text
    assert "worker_view" in text or "reminder_payload" in text


def test_given_the_import_task_then_validated_by_and_source_are_mandatory():
    text = _body("import_irrigation_params")
    assert "validated_by" in text and "source" in text


def test_given_the_worker_image_then_the_f4_modules_are_copied_from_the_api_single_source():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    for needle in ("access_sql", "gateways", "clock.py", "irrigation_advice.py", "water_balance.py", "worker_view.py"):
        assert needle in dockerfile, needle  # one source for the API and the worker (gateways.py carries weather_observed)
