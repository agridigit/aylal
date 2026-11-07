"""T062 - R4-A2, R4-A3: plan for tomorrow (offline-created, synced), reminder row, mark done, journal and DAR count it."""
import datetime as dt
import uuid

import httpx

from tests.e2e._f6 import BASE, TODAY, field_with_crop, owner_with_farm, unique_phone, product
from tests.helpers import sql

PHONE = unique_phone()


def test_given_an_operation_planned_offline_for_tomorrow_when_synced_and_done_then_it_counts_everywhere() -> None:
    tomorrow = TODAY + dt.timedelta(days=1)
    with httpx.Client(base_url=BASE, verify=False, timeout=60) as c:
        h, farm = owner_with_farm(c, PHONE)
        parcel, _ = field_with_crop(c, h, farm, "A", -7.60)
        pid = str(product("E2E Planifie 614", [dict(crop_slug="olive", max_dose=9, dar_days=10)]))
        rid = uuid.uuid4()
        op = {"op_id": str(uuid.uuid4()), "table": "operations", "kind": "put", "record_id": str(rid), "farm_id": farm, "base_version": 0,
              "fields": {"type": "phyto", "performed_on": tomorrow.isoformat(), "parcel_ids": [parcel], "product_id": pid, "dose": 1, "dose_unit": "L/ha"}}
        assert c.post("/sync/upload", json={"ops": [op]}, headers=h).json()["results"][0]["status"] == "applied"
        got = c.get(f"/farms/{farm}/operations/{rid}", headers=h).json()
        assert got["status"] == "planned" and got["overdue"] is False
        assert [(r["fire_on"], r["state"]) for r in sql("SELECT fire_on, state FROM operation_reminders WHERE operation_id=$1", rid)] == [(tomorrow, "scheduled")]
        harvest = f"/farms/{farm}/fields/{parcel}/earliest-harvest"
        assert c.get(harvest, headers=h).json()["date"] is None
        moved = c.post(f"/farms/{farm}/operations/{rid}/reschedule", json={"performed_on": (tomorrow + dt.timedelta(days=1)).isoformat()}, headers=h)
        assert moved.status_code == 200 and moved.json()["status"] == "planned"
        done = c.post(f"/farms/{farm}/operations/{rid}/done", headers=h)
        assert done.status_code == 200 and done.json()["status"] == "validated"
        assert c.get(f"/farms/{farm}/operations", params={"status": "validated"}, headers=h).json()["items"][0]["id"] == str(rid)
        assert c.get(harvest, headers=h).json()["limiting_product"] == "E2E Planifie 614"
        assert sql("SELECT state FROM operation_reminders WHERE operation_id=$1", rid)[0][0] == "done"
        assert sql("SELECT count(*) FROM operations_done WHERE operation_id=$1", rid)[0][0] == 1
