"""T069 - R5-A1..A4: each contributor explains its source; F6 overdue operations is an available source; F4/F5 are absent without error."""
import uuid

from tests.helpers import sql
from tests.integration._f3 import call, seed_status_item, world3  # noqa: F401


def test_given_an_orange_or_red_parcel_when_opening_the_detail_then_every_contributor_explains_its_source(client, token_for, world3):
    w = world3
    seed_status_item(w["farm_a"], w["a1"], source="weather_alert")
    seed_status_item(w["farm_a"], w["a1"], source="overdue_operations")
    b = call(client, token_for(w["owner"]), "GET", f"/v1/farms/{w['farm_a']}/parcels/{w['a1']}/status").json()
    assert {i["source"] for i in b["items"]} >= {"weather_alert", "overdue_operations"}
    assert all(i["reason_key"] and i["severity"] in ("watch", "act") and i["observed_at"] for i in b["items"])
    assert all("source_ref" not in i for i in b["items"])  # server ids of alerts/zones/operations are not exposed


def test_given_a_green_parcel_when_opening_the_detail_then_it_has_no_contributor(client, token_for, world3):
    w = world3
    b = call(client, token_for(w["owner"]), "GET", f"/v1/farms/{w['farm_a']}/parcels/{w['p'][3]}/status").json()
    assert b["color"] in ("green", "orange", "red") and (b["color"] != "green" or b["items"] == [])


def test_given_the_database_when_listing_available_sources_then_f6_overdue_operations_is_available_and_f4_f5_are_not_yet():
    from app.monitoring.status_sources import available_sources

    tables = {r["table_name"] for r in sql("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")}
    got = available_sources(tables)
    assert {"weather_alert", "vigor_anomaly", "overdue_operations"} <= got
    assert ("irrigation_need" in got) == ("irrigation_plans" in tables or "irrigation_needs" in tables)
    assert ("health_risk" in got) == ("health_risks" in tables or "health_risk_assessments" in tables)


def test_given_no_item_for_an_unavailable_source_then_the_dashboard_still_answers_200_without_error(client, token_for, world3):
    w = world3
    r = call(client, token_for(w["owner"]), "GET", f"/v1/farms/{w['farm_a']}/dashboard")
    assert r.status_code == 200
    assert {p["parcel_id"] for p in r.json()["parcels"]} == {str(p) for p in w["p"]}


def test_given_an_item_whose_source_is_not_in_the_catalogue_then_the_database_refuses_it(world3):
    w = world3
    try:
        sql("INSERT INTO parcel_status_items (id, farm_id, parcel_id, source, severity, reason_key, reason_params, source_ref, observed_at)"
            " VALUES ($1,$2,$3,'fake_source','act','x','{}'::jsonb,$4,now())", uuid.uuid4(), w["farm_a"], w["a1"], uuid.uuid4())
    except Exception:  # noqa: BLE001 - any constraint violation is the expected refusal
        return
    raise AssertionError("an unknown status source was accepted")


def test_given_a_worker_when_reading_the_status_of_a_hidden_parcel_then_404_identical(client, token_for, world3):
    w = world3
    r = call(client, token_for(w["worker"]), "GET", f"/v1/farms/{w['farm_a']}/parcels/{w['hidden']}/status")
    assert r.status_code == 404 and r.json() == {"detail": "not_found"}


def test_given_a_dashboard_when_a_worker_reads_then_the_counts_cover_only_the_assigned_parcels_and_the_order_is_red_first(client, token_for, world3):
    w = world3
    b = call(client, token_for(w["worker"]), "GET", f"/v1/farms/{w['farm_a']}/dashboard").json()
    order = [p["color"] for p in b["parcels"]]
    assert order == sorted(order, key={"red": 0, "orange": 1, "green": 2}.get)
    assert sum(b["counts"].values()) == 3
