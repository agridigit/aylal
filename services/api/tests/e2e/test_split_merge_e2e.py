"""T059 - split then merge on the running stack, areas and attachments checked, offline replay (R5-A1, R5-A2)."""
import uuid

import httpx

from tests.e2e._f2 import BASE, fresh, owner_with_farm, square

PHONE = "+212677006603"
EDGE = -7.60 + 0.002


def test_given_a_field_when_splitting_then_merging_with_a_neighbour_then_areas_and_attachments_are_consistent() -> None:
    fresh(PHONE)
    with httpx.Client(base_url=BASE, verify=False, timeout=60) as c:
        h, farm = owner_with_farm(c, PHONE)
        a = c.post(f"/farms/{farm}/fields", json={"name": "A", "geometry": square(-7.60)}, headers=h).json()
        b = c.post(f"/farms/{farm}/fields", json={"name": "B", "geometry": square(EDGE)}, headers=h).json()
        crop = next(x for x in c.get("/crops", headers=h).json()["items"] if x["slug"] == "durum-wheat")
        s = c.post(f"/farms/{farm}/fields/{b['id']}/seasons", json={"crop_id": crop["id"], "sowing_date": "2026-01-10", "started_at": "2026-01-10"}, headers=h)
        assert s.status_code == 201
        blk = c.post(f"/farms/{farm}/fields/{a['id']}/blocks", json={"name": "N", "kind": "block", "geometry": square(-7.60, 33.57, 0.0009)}, headers=h)
        assert blk.status_code == 201 and blk.json()["field_id"] == a["id"] and blk.json()["area_calc_ha"] > 0
        r = c.post(f"/farms/{farm}/fields/merge", json={"survivor_id": a["id"], "merged_ids": [b["id"]]}, headers=h)
        assert r.status_code == 200, r.text
        assert abs(r.json()["area_calc_ha"] - (a["area_calc_ha"] + b["area_calc_ha"])) / r.json()["area_calc_ha"] < 0.005
        assert [x["id"] for x in c.get(f"/farms/{farm}/fields/{a['id']}/seasons", headers=h).json()["items"]] == [s.json()["id"]]
        assert c.get(f"/farms/{farm}/fields/{b['id']}", headers=h).status_code == 404
        assert [x["id"] for x in c.get(f"/farms/{farm}/fields/archived", headers=h).json()["items"]] == [b["id"]]
        assert len(c.get(f"/farms/{farm}/fields/{a['id']}/blocks", headers=h).json()["items"]) == 1
    fresh(PHONE)


def test_given_a_merge_recorded_offline_when_the_queue_is_replayed_twice_then_it_is_applied_once() -> None:
    fresh(PHONE)
    with httpx.Client(base_url=BASE, verify=False, timeout=60) as c:
        h, farm = owner_with_farm(c, PHONE)
        a = c.post(f"/farms/{farm}/fields", json={"name": "A", "geometry": square(-7.60)}, headers=h).json()
        b = c.post(f"/farms/{farm}/fields", json={"name": "B", "geometry": square(EDGE)}, headers=h).json()
        cmd = {"op_id": str(uuid.uuid4()), "table": "field_commands", "kind": "put", "record_id": str(uuid.uuid4()), "farm_id": farm,
               "base_version": 0, "fields": {"kind": "merge", "payload": {"survivor_id": a["id"], "merged_ids": [b["id"]]}}}
        first = c.post("/sync/upload", json={"ops": [cmd]}, headers=h)
        again = c.post("/sync/upload", json={"ops": [cmd]}, headers=h)
        assert first.json()["results"][0]["status"] == "applied" and again.json()["results"][0]["status"] == "duplicate"
        assert [x["id"] for x in c.get(f"/farms/{farm}/fields", headers=h).json()["items"]] == [a["id"]]
    fresh(PHONE)
