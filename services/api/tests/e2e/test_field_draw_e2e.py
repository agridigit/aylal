"""T026 - draw a field by taps then by GPS on the running stack (R1-A1 to R1-A5)."""
import uuid

import httpx

from tests.e2e._f2 import BASE, fresh, owner_with_farm, square
from tests.helpers import sql

PHONE = "+212677006601"


def test_given_taps_and_gps_drawings_when_created_and_synced_then_areas_are_computed_and_a_crossing_is_refused() -> None:
    fresh(PHONE)
    with httpx.Client(base_url=BASE, verify=False, timeout=30) as c:
        h, farm = owner_with_farm(c, PHONE)
        taps = c.post(f"/farms/{farm}/fields", json={"name": "Taps", "geometry": square(), "source": "draw_taps"}, headers=h)
        assert taps.status_code == 201 and taps.json()["area_calc_ha"] > 0
        bow = {"type": "Polygon", "coordinates": [[[-7.6, 33.57], [-7.598, 33.572], [-7.598, 33.57], [-7.6, 33.572], [-7.6, 33.57]]]}
        assert c.post(f"/farms/{farm}/fields", json={"name": "Bow", "geometry": bow}, headers=h).status_code == 422
        assert c.post(f"/farms/{farm}/fields", json={"name": "Paris", "geometry": square(2.35, 48.85)}, headers=h).status_code == 422
        declared = c.post(f"/farms/{farm}/fields", json={"name": "Decl", "geometry": square(-7.7), "area_declared_ha": 7.5}, headers=h).json()
        assert declared["area_declared_ha"] == 7.5 and declared["area_calc_ha"] != 7.5
        # GPS field created offline, replayed when the network returns
        fid = str(uuid.uuid4())
        op = {"op_id": str(uuid.uuid4()), "table": "parcels", "kind": "put", "record_id": fid, "farm_id": farm, "base_version": 0,
              "fields": {"name": "GPS", "geometry": square(-7.8), "source": "draw_gps", "gps_accuracy_m": 6, "area_calc_ha": 9999}}
        r = c.post("/sync/upload", json={"ops": [op]}, headers=h)
        assert r.status_code == 200 and r.json()["results"][0]["status"] == "applied"
        assert c.post("/sync/upload", json={"ops": [op]}, headers=h).json()["results"][0]["status"] == "duplicate"
        got = c.get(f"/farms/{farm}/fields/{fid}", headers=h).json()
        assert got["source"] == "draw_gps" and got["area_calc_ha"] < 100
    assert sql("SELECT count(*) FROM parcels WHERE farm_id=$1", uuid.UUID(farm))[0][0] == 3
    fresh(PHONE)
