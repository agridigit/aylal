"""T031c - hardening: retention follows max(performed_on, server recording date) and the longest of the chain; purge respects both."""
import datetime as dt
import uuid

from tests.helpers import auth, sql
from tests.integration._f6 import TODAY, add_operation, add_registry, op_body, world  # noqa: F401


def _plus_years(day, years):
    try:
        return day.replace(year=day.year + years)
    except ValueError:
        return day.replace(year=day.year + years, day=28)


def _create_phyto(client, token_for, w, performed_on):
    body = op_body([w["a1"]], type="phyto", free_product_name="Maison", dose=2, dose_unit="L/ha", performed_on=performed_on.isoformat())
    r = client.post(f"/v1/farms/{w['farm_a']}/operations", headers=auth(token_for(w["owner"])), json=body)
    assert r.status_code == 201, r.text
    return uuid.UUID(r.json()["id"])


def _retains(oid):
    return [r[0] for r in sql("SELECT retain_until FROM registry_entries WHERE operation_id=$1 ORDER BY recorded_at, id", oid)]


def test_given_an_operation_backdated_ten_years_then_retention_runs_from_the_recording_date(client, token_for, world):
    w = world
    oid = _create_phyto(client, token_for, w, _plus_years(TODAY, -10))
    got = _retains(oid)
    assert len(got) == 1
    assert got[0] >= _plus_years(TODAY, 5) - dt.timedelta(days=1)


def test_given_a_future_dated_operation_marked_done_then_retention_runs_from_performed_on(client, token_for, world):
    w = world
    future = TODAY + dt.timedelta(days=200)
    body = op_body([w["a1"]], type="phyto", free_product_name="Maison", dose=2, dose_unit="L/ha", performed_on=future.isoformat())
    r = client.post(f"/v1/farms/{w['farm_a']}/operations", headers=auth(token_for(w["owner"])), json=body)
    assert r.status_code == 201, r.text
    oid = uuid.UUID(r.json()["id"])
    assert client.post(f"/v1/farms/{w['farm_a']}/operations/{oid}/done", headers=auth(token_for(w["owner"]))).status_code == 200
    assert _retains(oid) == [_plus_years(future, 5)]


def test_given_a_correction_chain_then_every_entry_keeps_the_longest_retain_until(client, token_for, world):
    w = world
    future = TODAY + dt.timedelta(days=200)
    longest = _plus_years(future, 5)
    body = op_body([w["a1"]], type="phyto", free_product_name="Maison", dose=2, dose_unit="L/ha", performed_on=future.isoformat())
    oid = uuid.UUID(client.post(f"/v1/farms/{w['farm_a']}/operations", headers=auth(token_for(w["owner"])), json=body).json()["id"])
    h = auth(token_for(w["owner"]))
    assert client.post(f"/v1/farms/{w['farm_a']}/operations/{oid}/done", headers=h).status_code == 200
    # the date is corrected back to today: the new application must not shorten the chain
    r = client.patch(f"/v1/farms/{w['farm_a']}/operations/{oid}", headers=h, json={"performed_on": TODAY.isoformat()})
    assert r.status_code == 200, r.text
    got = _retains(oid)
    assert len(got) == 3  # application, reversal, application
    assert all(d >= longest for d in got), got


def test_given_a_cancellation_then_the_reversal_keeps_the_retain_until_of_the_application(client, token_for, world):
    w = world
    oid = _create_phyto(client, token_for, w, _plus_years(TODAY, -10))
    applied = _retains(oid)[0]
    assert client.post(f"/v1/farms/{w['farm_a']}/operations/{oid}/cancel", headers=auth(token_for(w["owner"]))).status_code == 200
    got = _retains(oid)
    assert len(got) == 2 and got[1] >= applied and got[1] >= _plus_years(TODAY, 5) - dt.timedelta(days=1)


def test_given_a_chain_with_an_unexpired_member_when_purging_then_no_entry_of_the_chain_goes(world):
    w = world
    oid = add_operation(w["farm_a"], w["owner"], w["a1"], type_="phyto")
    old = add_registry(w["farm_a"], oid, w["a1"], retain_until=TODAY - dt.timedelta(days=1))
    rev = add_registry(w["farm_a"], oid, w["a1"], kind="reversal", supersedes_id=old, retain_until=TODAY + dt.timedelta(days=30))
    new = add_registry(w["farm_a"], oid, w["a1"], retain_until=TODAY + dt.timedelta(days=30))
    sql("SELECT purge_expired_registry($1::date)", TODAY)
    ids = {r[0] for r in sql("SELECT id FROM registry_entries WHERE operation_id=$1", oid)}
    assert {old, rev, new} <= ids


def test_given_a_fully_expired_chain_when_purging_then_it_goes_as_a_whole(world):
    w = world
    oid = add_operation(w["farm_a"], w["owner"], w["a1"], type_="phyto")
    gone = TODAY - dt.timedelta(days=1)
    old = add_registry(w["farm_a"], oid, w["a1"], performed_on=TODAY - dt.timedelta(days=3000), retain_until=gone)
    add_registry(w["farm_a"], oid, w["a1"], performed_on=TODAY - dt.timedelta(days=3000), kind="reversal", supersedes_id=old, retain_until=gone)
    sql("SELECT purge_expired_registry($1::date)", TODAY)
    assert sql("SELECT count(*) FROM registry_entries WHERE operation_id=$1", oid)[0][0] == 0


def test_given_a_row_recorded_today_with_a_legacy_short_retain_until_when_purging_then_it_is_kept(world):
    w = world
    oid = add_operation(w["farm_a"], w["owner"], w["a1"], type_="phyto")
    ten_years_ago = _plus_years(TODAY, -10)
    rid = add_registry(w["farm_a"], oid, w["a1"], performed_on=ten_years_ago, retain_until=_plus_years(ten_years_ago, 5))
    sql("SELECT purge_expired_registry($1::date)", TODAY)
    assert rid in {r[0] for r in sql("SELECT id FROM registry_entries WHERE operation_id=$1", oid)}
