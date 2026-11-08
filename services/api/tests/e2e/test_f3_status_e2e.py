"""T071 - R5-A1..A5 on the running stack with the real worker: weather + vigor + overdue operation -> colour, one-sentence reason, order, per-source detail, worker scope."""
import datetime as dt
import uuid

from tests.e2e._f3 import TODAY, client, run_job, setup_farm
from tests.helpers import sql
from tests.integration._f3 import seed_alert, seed_zone


def _overdue(farm, parcel):
    op, on = uuid.uuid4(), TODAY - dt.timedelta(days=3)
    sql("INSERT INTO operations (id, farm_id, type, performed_on, status) VALUES ($1,$2,'irrigation',$3,'planned')", op, farm, on)
    sql("INSERT INTO operation_parcels (id, farm_id, operation_id, parcel_id, type, performed_on, status) VALUES ($1,$2,$3,$4,'irrigation',$5,'planned')", uuid.uuid4(), farm, op, parcel, on)


def test_given_weather_vigor_and_an_overdue_operation_when_the_worker_computes_then_colours_order_reasons_and_per_source_details_are_served():
    # parcels: p0 assigned to the worker (orange), p1 red, p2 green, p3 orange but hidden from the worker
    with client() as c:
        s = setup_farm(c, 4, worker=True, hidden=3)
        farm = uuid.UUID(s["farm"])
        p0, p1, p2, p3 = (uuid.UUID(p) for p in s["parcels"])
        seed_zone(farm, p0)
        _overdue(farm, p0)
        seed_alert(farm, p1, type_="frost", severity="critical")
        _overdue(farm, p3)
        run_job("recompute_status", farm_id=farm)

        dash = c.get(f"/farms/{farm}/dashboard", headers=s["oh"]).json()
        colors = [(p["parcel_id"], p["color"]) for p in dash["parcels"]]
        assert colors[0] == (str(p1), "red") and colors[-1] == (str(p2), "green") and {c for _, c in colors[1:3]} == {"orange"}
        assert dash["counts"] == {"red": 1, "orange": 2, "green": 1}
        assert all(p["reason_key"] for p in dash["parcels"]) and next(p for p in dash["parcels"] if p["parcel_id"] == str(p2))["reason_key"] == "status.nothing_to_do"

        detail = c.get(f"/farms/{farm}/parcels/{p0}/status", headers=s["oh"]).json()
        assert {i["source"] for i in detail["items"]} == {"vigor_anomaly", "overdue_operations"} and detail["color"] == "orange"
        assert all(i["reason_key"] and i["observed_at"] for i in detail["items"])

        wdash = c.get(f"/farms/{farm}/dashboard", headers=s["wh"]).json()
        assert {p["parcel_id"] for p in wdash["parcels"]} == {str(p0)} and wdash["counts"] == {"red": 0, "orange": 1, "green": 0}
        assert c.get(f"/farms/{farm}/parcels/{p1}/status", headers=s["wh"]).json() == {"detail": "not_found"}


def test_given_sources_f4_and_f5_not_delivered_when_the_worker_computes_then_the_dashboard_answers_without_error():
    with client() as c:
        s = setup_farm(c, 1)
        run_job("recompute_status", farm_id=uuid.UUID(s["farm"]))
        r = c.get(f"/farms/{s['farm']}/dashboard", headers=s["oh"])
        assert r.status_code == 200 and r.json()["parcels"][0]["color"] == "green" and r.json()["parcels"][0]["reason_key"] == "status.nothing_to_do"


def test_given_an_archived_parcel_when_the_worker_computes_then_it_disappears_from_the_dashboard():
    with client() as c:
        s = setup_farm(c, 2)
        farm = uuid.UUID(s["farm"])
        seed_alert(farm, uuid.UUID(s["parcels"][0]), severity="critical")
        run_job("recompute_status", farm_id=farm)
        assert c.delete(f"/farms/{farm}/fields/{s['parcels'][0]}", headers=s["oh"]).status_code == 204
        run_job("recompute_status", farm_id=farm)
        ids = {p["parcel_id"] for p in c.get(f"/farms/{farm}/dashboard", headers=s["oh"]).json()["parcels"]}
        assert s["parcels"][0] not in ids and s["parcels"][1] in ids
