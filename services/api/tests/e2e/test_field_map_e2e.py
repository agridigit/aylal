"""T053 - a farm of 50 fields: list and card on the running stack (R4-A1, R4-A3)."""
import uuid

import httpx

from tests.e2e._f2 import BASE, fresh, owner_with_farm, square
from tests.helpers import sql

PHONE = "+212677006604"


def test_given_a_farm_of_50_fields_when_listing_then_all_are_returned_with_status_and_the_card_opens() -> None:
    fresh(PHONE)
    with httpx.Client(base_url=BASE, verify=False, timeout=120) as c:
        h, farm = owner_with_farm(c, PHONE)
        ids = []
        for i in range(50):
            r = c.post(f"/farms/{farm}/fields", json={"name": f"F{i:02d}", "geometry": square(-8.0 + i * 0.003)}, headers=h)
            assert r.status_code == 201, r.text
            ids.append(r.json()["id"])
        sql("UPDATE parcels SET status_summary='ok' WHERE id=$1", uuid.UUID(ids[0]))
        items = c.get(f"/farms/{farm}/fields", headers=h).json()["items"]
        assert len(items) == 50
        by_id = {f["id"]: f for f in items}
        assert by_id[ids[0]]["status_summary"] == "ok" and by_id[ids[1]]["status_summary"] is None
        card = c.get(f"/farms/{farm}/fields/{ids[7]}", headers=h)
        assert card.status_code == 200 and card.json()["name"] == "F07"
        assert c.delete(f"/farms/{farm}/fields/{ids[7]}", headers=h).status_code == 204
        assert len(c.get(f"/farms/{farm}/fields", headers=h).json()["items"]) == 49
    fresh(PHONE)
