"""T037 - one field per reference crop plus a free crop on the running stack (R2-A1 to R2-A5)."""
import httpx

from tests.e2e._f2 import BASE, fresh, owner_with_farm, square

PHONE = "+212677006602"
PERENNIAL = {"olive", "citrus", "avocado", "date-palm", "almond", "grape", "berries"}


def test_given_the_16_crops_and_a_free_crop_when_creating_a_field_each_then_every_campaign_is_started() -> None:
    fresh(PHONE)
    with httpx.Client(base_url=BASE, verify=False, timeout=60) as c:
        h, farm = owner_with_farm(c, PHONE)
        crops = [x for x in c.get("/crops", headers=h).json()["items"] if not x["slug"].startswith("fx_")]  # F3 fixture crops are never deleted
        assert len(crops) == 16 and all(x["photo_key"] for x in crops)
        for i, crop in enumerate(crops):
            f = c.post(f"/farms/{farm}/fields", json={"name": crop["slug"], "geometry": square(-7.9 + i * 0.004)}, headers=h)
            assert f.status_code == 201, f.text
            date = {"planting_year": 2015} if crop["cycle"] == "perennial" else {"sowing_date": "2026-01-10"}
            s = c.post(f"/farms/{farm}/fields/{f.json()['id']}/seasons", json={"crop_id": crop["id"], "started_at": "2026-01-10", **date}, headers=h)
            assert s.status_code == 201, (crop["slug"], s.text)
        free = c.post(f"/farms/{farm}/crops", json={"name": "Safran", "cycle": "annual"}, headers=h)
        assert free.status_code == 201
        f = c.post(f"/farms/{farm}/fields", json={"name": "Safran", "geometry": square(-7.5)}, headers=h).json()
        s = c.post(f"/farms/{farm}/fields/{f['id']}/seasons", json={"crop_id": free.json()["id"], "sowing_date": "2026-02-01", "started_at": "2026-02-01"}, headers=h)
        assert s.status_code == 201 and s.json()["stage_estimated"] is None
        wheat = next(x for x in crops if x["slug"] == "durum-wheat")
        w = c.post(f"/farms/{farm}/fields", json={"name": "W", "geometry": square(-7.4)}, headers=h).json()
        ws = c.post(f"/farms/{farm}/fields/{w['id']}/seasons", json={"crop_id": wheat["id"], "sowing_date": "2026-01-01", "started_at": "2026-01-01"}, headers=h).json()
        assert ws["stage_estimated"]
        fixed = c.patch(f"/farms/{farm}/fields/{w['id']}/seasons/{ws['id']}", json={"stage_corrected": "heading"}, headers=h)
        assert fixed.json()["stage_corrected"] == "heading"
    fresh(PHONE)
