"""T067 - chain two campaigns and read the first one on the running stack (R6-A1 to R6-A3)."""
import httpx

from tests.e2e._f2 import BASE, fresh, owner_with_farm, square

PHONE = "+212677006604"


def test_given_two_chained_campaigns_when_reading_the_history_then_the_first_is_closed_and_consultable() -> None:
    fresh(PHONE)
    with httpx.Client(base_url=BASE, verify=False, timeout=60) as c:
        h, farm = owner_with_farm(c, PHONE)
        crops = {x["slug"]: x for x in c.get("/crops", headers=h).json()["items"]}
        f = c.post(f"/farms/{farm}/fields", json={"name": "A", "geometry": square(-7.60)}, headers=h).json()
        url = f"/farms/{farm}/fields/{f['id']}/seasons"
        first = c.post(url, json={"crop_id": crops["durum-wheat"]["id"], "sowing_date": "2025-10-10", "started_at": "2025-10-10"}, headers=h).json()
        dup = c.post(url, json={"crop_id": crops["durum-wheat"]["id"], "sowing_date": "2025-11-10", "started_at": "2025-11-10"}, headers=h)
        assert dup.status_code == 409
        second = c.post(url, json={"crop_id": crops["olive"]["id"], "planting_year": 2015, "started_at": "2026-06-01", "close_ids": [first["id"]]}, headers=h)
        assert second.status_code == 201, second.text
        old = c.get(f"{url}/{first['id']}", headers=h).json()
        assert old["ended_at"] == "2026-06-01"
        third = c.post(url, json={"crop_id": crops["almond"]["id"], "planting_year": 2018, "started_at": "2026-06-02"}, headers=h)
        assert third.status_code == 201  # intercropping: olive and almond active together
        items = c.get(url, headers=h).json()["items"]
        assert len(items) == 3 and sum(1 for s in items if s["ended_at"] is None) == 2
    fresh(PHONE)
