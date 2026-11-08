"""T029 - foundations on the running stack: a worker with 3 parcels out of 10 only sees their scope; archiving removes a parcel;
empty gateways read as 'unavailable'. Phone numbers are unique per run and no protected table is ever deleted from."""
import httpx

from tests.e2e._f2 import BASE, CASA, square, unique_phone
from tests.integration._f3 import seed_alert, seed_status, seed_zone


def _login(c, phone):
    assert c.post("/auth/otp/request", json={"phone": phone}).status_code == 202
    return c.post("/auth/otp/verify", json={"phone": phone, "code": "000000"}).json()


def test_given_a_worker_with_3_of_10_parcels_when_reading_everything_then_only_their_scope_is_served_and_archiving_hides_a_parcel() -> None:
    owner_phone, worker_phone = unique_phone(), unique_phone()
    with httpx.Client(base_url=BASE, verify=False, timeout=60) as c:
        owner = _login(c, owner_phone)
        oh = {"Authorization": f"Bearer {owner['access_token']}"}
        farm = c.post("/farms", json={"name": "Atlas", "location": CASA}, headers=oh).json()["id"]
        assert c.post(f"/farms/{farm}/invitations", json={"phone": worker_phone, "role": "worker"}, headers=oh).status_code == 201
        worker = _login(c, worker_phone)
        wh = {"Authorization": f"Bearer {worker['access_token']}"}
        uid = worker["user"]["id"]
        parcels = [c.post(f"/farms/{farm}/fields", json={"name": f"P{i}", "geometry": square(-7.60 + i * 0.01)}, headers=oh).json()["id"] for i in range(10)]
        mine, hidden = parcels[:3], parcels[5]
        assert c.put(f"/farms/{farm}/members/{uid}/parcels", json={"parcel_ids": mine}, headers=oh).status_code == 200
        colors = {0: "red", 1: "orange", 2: "green", 5: "red"}
        for i, p in enumerate(parcels):
            seed_status(farm, p, colors.get(i, "green"), rank=i)
        seed_alert(farm, mine[0])
        seed_alert(farm, hidden)
        seed_zone(farm, mine[0])
        seed_zone(farm, hidden)

        dash = c.get(f"/farms/{farm}/dashboard", headers=wh)
        assert dash.status_code == 200, dash.text
        assert {p["parcel_id"] for p in dash.json()["parcels"]} == set(mine)
        assert dash.json()["counts"] == {"red": 1, "orange": 1, "green": 1}
        assert {a["parcel_id"] for a in c.get(f"/farms/{farm}/alerts", headers=wh).json()} == {mine[0]}
        assert {z["parcel_id"] for z in c.get(f"/farms/{farm}/zones", headers=wh).json()} == {mine[0]}
        assert {i["parcel_id"] for i in c.get(f"/farms/{farm}/summary/today", headers=wh).json()["items"]} <= set(mine)
        assert c.get(f"/farms/{farm}/parcels/{hidden}/status", headers=wh).json() == {"detail": "not_found"}
        assert c.get(f"/farms/{farm}/dashboard", headers=oh).json()["counts"] == {"red": 2, "orange": 1, "green": 7}

        assert c.delete(f"/farms/{farm}/fields/{mine[0]}", headers=oh).status_code == 204  # archive
        after = c.get(f"/farms/{farm}/dashboard", headers=wh).json()
        assert {p["parcel_id"] for p in after["parcels"]} == set(mine[1:]) and after["counts"] == {"red": 0, "orange": 1, "green": 1}
        assert c.get(f"/farms/{farm}/alerts", headers=wh).json() == []
        assert c.get(f"/farms/{farm}/parcels/{mine[0]}/status", headers=wh).status_code == 404

        weather = c.get(f"/farms/{farm}/weather", headers=wh)
        assert weather.status_code == 200 and weather.json()["availability"] == "unavailable"
        assert weather.json()["reason"] == "gateway_not_configured" and not weather.json().get("days")
