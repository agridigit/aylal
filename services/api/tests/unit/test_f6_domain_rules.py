"""T007 - shared F6 domain rules (allocation, units, status machine) mirror the TS vectors."""
import json
import os
from datetime import date
from pathlib import Path

import pytest

DOMAIN_DIR = Path(os.environ.get("AYLAL_DOMAIN_DIR", "/packages/domain"))


def _vec(name: str):
    return json.loads((DOMAIN_DIR / "vectors" / name).read_text(encoding="utf-8"))

ALLOC = _vec("f6_allocation.json")
UNITS = _vec("f6_units.json")
MACHINE = _vec("f6_status_machine.json")


@pytest.mark.parametrize("v", ALLOC, ids=lambda v: v["name"])
def test_given_a_total_and_areas_when_allocating_then_shares_match_the_vector(v):
    from app.domain.allocation import allocate

    out = allocate(v["total"], v["areas"])
    assert [float(x) for x in out] == v["expected"]
    assert round(sum(float(x) for x in out), 3) == v["total"]


@pytest.mark.parametrize("v", UNITS, ids=lambda v: f"{v['from']}->{v['to']}:{v['value']}")
def test_given_a_dose_when_converting_units_then_it_matches_the_vector(v):
    from app.domain.units import convert_dose

    got = convert_dose(v["value"], v["from"], v["to"])
    assert (got is None) if v["expected"] is None else (float(got) == v["expected"])


@pytest.mark.parametrize("t", MACHINE["transitions"], ids=lambda t: f"{t['from']}:{t['action']}:{t['role']}")
def test_given_a_status_when_a_role_acts_then_the_transition_matches_the_vector(t):
    from app.domain.operation_rules import next_status

    assert next_status(t["from"], t["action"], t["role"]) == t["to"]


@pytest.mark.parametrize("i", MACHINE["initial"], ids=lambda i: f"{i['role']}:{i['performed_on']}")
def test_given_a_creation_date_and_role_then_the_initial_status_matches_the_vector(i):
    from app.domain.operation_rules import initial_status

    assert initial_status(date.fromisoformat(i["performed_on"]), date.fromisoformat(MACHINE["today"]), i["role"]) == i["status"]


@pytest.mark.parametrize("o", MACHINE["overdue"], ids=lambda o: f"{o['status']}:{o['performed_on']}")
def test_given_a_planned_operation_in_the_past_then_it_is_overdue(o):
    from app.domain.operation_rules import is_overdue

    assert is_overdue(o["status"], date.fromisoformat(o["performed_on"]), date.fromisoformat(MACHINE["today"])) is o["overdue"]
