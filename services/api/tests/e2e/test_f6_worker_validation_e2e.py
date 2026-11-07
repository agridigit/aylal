"""T076 - R7-A1 to R7-A4 on the running stack: a worker records, the manager sees it "to validate", validates, then corrects;
the registry grows by compensating entries only."""
import httpx

from tests.e2e._f6 import BASE, body, field_with_crop, owner_with_farm, unique_phone
from tests.helpers import sql

OWNER, WORKER = unique_phone(), unique_phone()


def _login(c: httpx.Client, phone: str) -> dict:
    assert c.post("/auth/otp/request", json={"phone": phone}).status_code == 202
    return c.post("/auth/otp/verify", json={"phone": phone, "code": "000000"}).json()


def test_given_a_worker_entry_when_the_owner_validates_then_validated_and_a_correction_adds_compensating_entries_only() -> None:
    with httpx.Client(base_url=BASE, verify=False, timeout=60) as c:
        oh, farm = owner_with_farm(c, OWNER)
        parcel, _ = field_with_crop(c, oh, farm, "A", -7.60)
        assert c.post(f"/farms/{farm}/invitations", json={"phone": WORKER, "role": "worker"}, headers=oh).status_code == 201
        session = _login(c, WORKER)
        wh = {"Authorization": f"Bearer {session['access_token']}"}
        assert c.put(f"/farms/{farm}/members/{session['user']['id']}/parcels", json={"parcel_ids": [parcel]}, headers=oh).status_code == 200

        made = c.post(f"/farms/{farm}/operations", headers=wh, json=body([parcel], type="phyto", free_product_name="Maison", dose=2, dose_unit="L/ha"))
        assert made.status_code == 201, made.text
        oid = made.json()["id"]
        assert made.json()["status"] == "pending_validation"
        queue = c.get(f"/farms/{farm}/operations", headers=oh, params={"status": "pending_validation"}).json()["items"]
        assert [i["id"] for i in queue] == [oid]
        assert c.post(f"/farms/{farm}/operations/{oid}/validate", headers=wh).status_code == 403
        assert c.get(f"/farms/{farm}/operations/{oid}/corrections", headers=wh).status_code == 403

        ok = c.post(f"/farms/{farm}/operations/{oid}/validate", headers=oh)
        assert ok.status_code == 200 and ok.json()["status"] == "validated"
        assert c.get(f"/farms/{farm}/operations", headers=oh, params={"status": "pending_validation"}).json()["items"] == []
        assert c.get(f"/farms/{farm}/operations/{oid}", headers=wh).json()["status"] == "validated"

        fixed = c.patch(f"/farms/{farm}/operations/{oid}", headers=oh, json={"dose": 3})
        assert fixed.status_code == 200, fixed.text
        history = c.get(f"/farms/{farm}/operations/{oid}/corrections", headers=oh).json()["items"]
        assert [(i["field"], i["before"], i["after"]) for i in history] == [("dose", 2, 3)]
        kinds = [r[0] for r in sql("SELECT entry_kind FROM registry_entries WHERE operation_id=$1::uuid ORDER BY recorded_at, id", oid)]
        assert kinds == ["application", "reversal", "application"]
        assert c.get(f"/farms/{farm}/registry", headers=wh).status_code == 403
        assert len(c.get(f"/farms/{farm}/registry", headers=oh).json()["items"]) == 1
