"""Client IP behind Caddy in the real stack: the limit is per client, not per proxy, and cannot be forged."""
import ipaddress

import httpx

from tests.helpers import sql

BASE = "https://proxy/v1"
PHONE = "+212677001133"


def test_given_the_stack_when_requesting_an_otp_then_the_recorded_ip_is_the_real_peer_not_the_proxy_nor_a_forged_value() -> None:
    sql("DELETE FROM otp_challenges WHERE phone_e164=$1", PHONE)
    forged = "203.0.113.77"
    with httpx.Client(base_url=BASE, verify=False, timeout=30) as c:
        r = c.post("/auth/otp/request", json={"phone": PHONE}, headers={"X-Real-IP": forged, "X-Forwarded-For": forged})
    assert r.status_code == 202
    recorded = sql("SELECT client_ip FROM otp_challenges WHERE phone_e164=$1", PHONE)[0][0]
    assert recorded is not None, "forwarded headers ignored: AYLAL_TRUSTED_PROXIES does not cover Caddy"
    assert recorded != forged
    assert ipaddress.ip_address(recorded).is_private
    proxy_ips = {a[4][0] for a in __import__("socket").getaddrinfo("proxy", 443)}
    assert recorded not in proxy_ips, "every client would share the proxy's bucket"
