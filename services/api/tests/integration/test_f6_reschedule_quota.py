"""Review finding 2: rescheduling takes the farm lock and re-checks the quotas when the year changes."""
import datetime as dt

import pytest

from tests.helpers import auth, sql
from tests.integration._f6 import TODAY, add_operation, world  # noqa: F401
from tests.integration.test_f6_quota_race import _race

NEXT_YEAR = TODAY.year + 1
TARGET = dt.date(NEXT_YEAR, 1, 20)


def _seed(farm, author, year, n, status):
    sql("INSERT INTO operations (id, farm_id, type, performed_on, status, author_id) "
        "SELECT gen_random_uuid(), $1, 'irrigation', make_date($5, 1, 1) + (g % 300), $4, $2 FROM generate_series(1, $3) g",
        farm, author, n, status, year)


def _resched(client, token_for, who, farm, op, day):
    return client.post(f"/v1/farms/{farm}/operations/{op}/reschedule", headers=auth(token_for(who)), json={"performed_on": day.isoformat()})


def _planned(w):
    return add_operation(w["farm_a"], w["owner"], w["a1"], status="planned", performed_on=TODAY)


def test_given_a_farm_at_the_yearly_cap_in_the_next_year_when_rescheduling_a_planned_operation_into_it_then_it_is_refused(client, token_for, world):
    w = world
    op = _planned(w)
    _seed(w["farm_a"], w["owner"], NEXT_YEAR, 20_000, "validated")
    r = _resched(client, token_for, w["owner"], w["farm_a"], op, TARGET)
    assert r.status_code in (413, 422), r.text
    assert "quota" in str(r.json()["detail"]), r.text
    assert sql("SELECT performed_on FROM operations WHERE id=$1", op)[0][0] == TODAY


def test_given_500_planned_operations_in_the_next_year_when_rescheduling_another_into_it_then_it_is_refused(client, token_for, world):
    w = world
    op = _planned(w)
    _seed(w["farm_a"], w["owner"], NEXT_YEAR, 500, "planned")
    r = _resched(client, token_for, w["owner"], w["farm_a"], op, TARGET)
    assert r.status_code in (413, 422), r.text
    assert "quota" in str(r.json()["detail"]), r.text
    assert sql("SELECT performed_on FROM operations WHERE id=$1", op)[0][0] == TODAY


def test_given_one_slot_left_in_the_next_year_when_two_reschedules_race_then_the_cap_is_never_exceeded(client, token_for, world):
    w = world
    ops = [_planned(w), _planned(w)]
    _seed(w["farm_a"], w["owner"], NEXT_YEAR, 19_999, "validated")
    from fastapi.testclient import TestClient

    from app.main import app
    tok = token_for(w["owner"])
    it = iter(ops)

    def one():
        op = next(it)
        with TestClient(app) as c:
            return c.post(f"/v1/farms/{w['farm_a']}/operations/{op}/reschedule", headers=auth(tok), json={"performed_on": TARGET.isoformat()}).status_code
    codes = _race(2, one)
    assert codes.count(200) == 1, codes
    assert sql("SELECT count(*) FROM operations WHERE farm_id=$1 AND performed_on >= make_date($2,1,1) AND performed_on < make_date($3,1,1)",
               w["farm_a"], NEXT_YEAR, NEXT_YEAR + 1)[0][0] == 20_000


def test_given_a_farm_at_the_planned_cap_when_rescheduling_within_the_same_year_then_it_is_not_blocked(client, token_for, world):
    w = world
    op = _planned(w)
    _seed(w["farm_a"], w["owner"], TODAY.year, 499, "planned")
    same_year = dt.date(TODAY.year, 12, 31)
    if same_year <= TODAY:
        pytest.skip("last day of the year")
    r = _resched(client, token_for, w["owner"], w["farm_a"], op, same_year)
    assert r.status_code == 200, r.text
    assert sql("SELECT performed_on FROM operations WHERE id=$1", op)[0][0] == same_year


def test_given_room_in_the_next_year_when_rescheduling_into_it_then_the_operation_moves(client, token_for, world):
    w = world
    op = _planned(w)
    r = _resched(client, token_for, w["owner"], w["farm_a"], op, TARGET)
    assert r.status_code == 200, r.text
    assert sql("SELECT performed_on FROM operations WHERE id=$1", op)[0][0] == TARGET
