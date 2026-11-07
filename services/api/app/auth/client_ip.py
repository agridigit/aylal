"""Client IP for rate limits: forwarded headers count only from a trusted proxy (behaviour of F1)."""
import ipaddress

from fastapi import Request

from app.config import get_settings


def client_ip(request: Request) -> str | None:
    """Rate-limit IP: forwarded headers count only from a trusted proxy; unknown -> None (no shared bucket)."""
    host = request.client.host if request.client else None
    if not host:
        return None
    peer = _ip(host)
    trusted = [n for n in (_net(p) for p in get_settings().trusted_proxies) if n is not None]
    if peer is None or not any(peer in n for n in trusted):
        return host  # the socket peer itself: forwarded headers are not trusted
    real = _ip(request.headers.get("x-real-ip"))
    if real is not None:
        return str(real)
    for hop in reversed(request.headers.get("x-forwarded-for", "").split(",")):  # rightmost untrusted hop
        addr = _ip(hop.strip())
        if addr is None:
            return None
        if not any(addr in n for n in trusted):
            return str(addr)
    return host if request.headers.get("x-forwarded-for") else None  # every hop trusted: the socket peer


def _ip(value: str | None) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    try:
        return ipaddress.ip_address(value) if value else None
    except ValueError:
        return None


def _net(value: str) -> ipaddress.IPv4Network | ipaddress.IPv6Network | None:
    try:
        return ipaddress.ip_network(value, strict=False)
    except ValueError:
        return None
