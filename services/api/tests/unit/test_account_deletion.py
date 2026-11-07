"""T053 - 30-day deletion deadline and owner-with-members impact (R8-A1, R8-A3)."""
import datetime as dt

from app.domain.account_deletion import DELETION_GRACE_DAYS, deletion_deadline, deletion_impact

T0 = dt.datetime(2026, 11, 7, 12, 0, tzinfo=dt.UTC)


def test_given_the_grace_period_then_it_is_30_days():
    assert DELETION_GRACE_DAYS == 30


def test_given_a_confirmed_request_when_computing_the_deadline_then_it_is_exactly_30_days_later():
    assert deletion_deadline(T0) == dt.datetime(2026, 12, 7, 12, 0, tzinfo=dt.UTC)


def test_given_a_request_across_a_month_end_when_computing_the_deadline_then_no_day_is_lost():
    assert deletion_deadline(dt.datetime(2026, 1, 31, 8, 0, tzinfo=dt.UTC)) == dt.datetime(2026, 3, 2, 8, 0, tzinfo=dt.UTC)


def test_given_an_owner_of_a_farm_with_other_members_when_computing_impact_then_the_farm_is_listed():
    farms = [{"farm_id": "f1", "name": "Atlas", "role": "owner", "other_members": 2}]
    assert deletion_impact(farms) == [{"farm_id": "f1", "name": "Atlas", "other_members": 2}]


def test_given_a_sole_owner_when_computing_impact_then_nothing_is_listed():
    assert deletion_impact([{"farm_id": "f1", "name": "A", "role": "owner", "other_members": 0}]) == []


def test_given_a_manager_or_worker_with_other_members_when_computing_impact_then_nothing_is_listed():
    farms = [{"farm_id": "f1", "name": "A", "role": r, "other_members": 3} for r in ("manager", "worker")]
    assert deletion_impact(farms) == []
