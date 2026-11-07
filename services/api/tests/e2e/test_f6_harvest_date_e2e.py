"""T056 - SC-003: DAR 21 days -> D+21; two products -> the longest applies; cancelling restores harvestability."""
import datetime as dt

import httpx

from tests.e2e._f6 import BASE, TODAY, body, field_with_crop, fresh, owner_with_farm, product

PHONE = "+212677006613"


def test_given_treatments_with_different_intervals_when_reading_the_parcel_then_the_longest_remaining_one_applies() -> None:
    fresh(PHONE)
    with httpx.Client(base_url=BASE, verify=False, timeout=60) as c:
        h, farm = owner_with_farm(c, PHONE)
        parcel, _ = field_with_crop(c, h, farm, "A", -7.60)
        url = f"/farms/{farm}/fields/{parcel}/earliest-harvest"
        assert c.get(url, headers=h).json()["harvestable_now"] is True
        p21 = str(product("E2E Vingt 613", [dict(crop_slug="olive", max_dose=9, dar_days=21)]))
        p7 = str(product("E2E Sept 613", [dict(crop_slug="olive", max_dose=9, dar_days=7)]))
        one = c.post(f"/farms/{farm}/operations", headers=h, json=body([parcel], type="phyto", product_id=p21, dose=1, dose_unit="L/ha"))
        assert one.status_code == 201, one.text
        assert c.get(url, headers=h).json()["date"] == (TODAY + dt.timedelta(days=21)).isoformat()
        c.post(f"/farms/{farm}/operations", headers=h, json=body([parcel], type="phyto", product_id=p7, dose=1, dose_unit="L/ha"))
        assert c.get(url, headers=h).json()["date"] == (TODAY + dt.timedelta(days=21)).isoformat()
        assert c.post(f"/farms/{farm}/operations/{one.json()['id']}/cancel", headers=h).status_code == 200
        assert c.get(url, headers=h).json()["date"] == (TODAY + dt.timedelta(days=7)).isoformat()
    fresh(PHONE)
