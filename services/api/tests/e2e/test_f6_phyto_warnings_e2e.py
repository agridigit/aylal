"""T046 - SC-002: dose above max, crop not authorised and max applications: 3 warnings land in the registry."""
import httpx

from tests.e2e._f6 import BASE, body, field_with_crop, fresh, owner_with_farm, product

PHONE = "+212677006612"


def test_given_three_non_compliant_treatments_when_reading_the_registry_then_the_three_warnings_are_on_their_lines() -> None:
    fresh(PHONE)
    with httpx.Client(base_url=BASE, verify=False, timeout=60) as c:
        h, farm = owner_with_farm(c, PHONE)
        olive, season = field_with_crop(c, h, farm, "Olives", -7.60, "olive")
        wheat, _ = field_with_crop(c, h, farm, "Blé", -7.55, "durum-wheat")
        pid = str(product("E2E Cuprex 612", [dict(crop_slug="olive", max_dose=2, dar_days=14, max_applications=1)]))
        first = c.post(f"/farms/{farm}/operations", headers=h, json=body([olive], type="phyto", product_id=pid, dose=1, dose_unit="L/ha", season_id=season))
        assert first.status_code == 201, first.text
        over = c.post(f"/farms/{farm}/operations", headers=h, json=body([olive], type="phyto", product_id=pid, dose=5, dose_unit="L/ha", season_id=season))
        wrong_crop = c.post(f"/farms/{farm}/operations", headers=h, json=body([wheat], type="phyto", product_id=pid, dose=1, dose_unit="L/ha"))
        assert over.status_code == wrong_crop.status_code == 201
        entries = c.get(f"/farms/{farm}/registry", headers=h).json()["items"]
        found = {w["code"] for e in entries for w in e["warnings"]}
        assert {"dose_above_max", "max_applications_reached", "not_authorized_for_crop"} <= found
        assert len(entries) == 3
        harvest = c.get(f"/farms/{farm}/fields/{olive}/earliest-harvest", headers=h).json()
        assert harvest["limiting_product"] == "E2E Cuprex 612" and harvest["harvestable_now"] is False
    fresh(PHONE)
