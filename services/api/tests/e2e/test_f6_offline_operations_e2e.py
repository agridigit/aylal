"""T035 - R1-A2, SC-004, FR-015, FR-016: local entry -> /v1/sync/upload -> operation_parcels, 30 days replayed without loss."""
import datetime as dt
import uuid

import httpx

from tests.e2e._f6 import BASE, TODAY, field_with_crop, owner_with_farm, unique_phone
from tests.helpers import sql

PHONE = unique_phone()


def sync(farm, rid, day, parcel, **extra):
    return {"op_id": str(uuid.uuid4()), "table": "operations", "kind": "put", "record_id": str(rid), "farm_id": farm, "base_version": 0,
            "fields": {"type": "irrigation", "performed_on": day.isoformat(), "parcel_ids": [parcel], **extra}}


def test_given_thirty_days_of_offline_operations_when_the_network_returns_then_none_is_lost_or_duplicated_and_done_ones_are_readable() -> None:
    with httpx.Client(base_url=BASE, verify=False, timeout=60) as c:
        h, farm = owner_with_farm(c, PHONE)
        parcel, _ = field_with_crop(c, h, farm, "A", -7.60)
        ids = [uuid.uuid4() for _ in range(30)]
        queue = [sync(farm, rid, TODAY - dt.timedelta(days=i), parcel) for i, rid in enumerate(ids)]
        planned = sync(farm, uuid.uuid4(), TODAY + dt.timedelta(days=3), parcel)
        queue.append(planned)
        for _ in range(2):  # the second replay (flaky network) must not duplicate
            for i in range(0, len(queue), 20):
                assert c.post("/sync/upload", json={"ops": queue[i:i + 20]}, headers=h).status_code == 200
        assert sql("SELECT count(*) FROM operations WHERE farm_id=$1", uuid.UUID(farm))[0][0] == 31
        assert sql("SELECT count(*) FROM operation_parcels WHERE farm_id=$1", uuid.UUID(farm))[0][0] == 31
        cancelled = c.post(f"/farms/{farm}/operations/{planned['record_id']}/cancel", headers=h)
        assert cancelled.status_code == 200
        listed = c.get(f"/farms/{farm}/operations", params={"limit": 50}, headers=h).json()["items"]
        assert len(listed) == 31
        stable = sql("SELECT operation_id FROM operations_done WHERE farm_id=$1", uuid.UUID(farm))
        assert {r[0] for r in stable} == set(ids), "the stable F4/F8 read point lists done operations only"
