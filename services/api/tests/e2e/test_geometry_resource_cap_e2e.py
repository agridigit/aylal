"""T077 - giant ring posted through the proxy on the running stack: fast 422, no timeout (DoS)."""
import time

import httpx

from tests.e2e._f2 import BASE, fresh, owner_with_farm
from tests.integration.test_f2_geometry_resource_cap import giant

PHONE = "+212677006690"


def test_given_a_giant_ring_when_posting_a_field_through_the_proxy_then_422_arrives_fast() -> None:
    fresh(PHONE)
    with httpx.Client(base_url=BASE, verify=False, timeout=10) as c:
        h, farm = owner_with_farm(c, PHONE)
        start = time.perf_counter()
        r = c.post(f"/farms/{farm}/fields", json={"name": "Giant", "geometry": giant(100_000)}, headers=h)
        assert r.status_code == 422
        assert time.perf_counter() - start < 2.0
    fresh(PHONE)
