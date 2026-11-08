"""Gateways to the external services hosted in Morocco (weather, imagery, optional push). G5.

Self-contained on purpose (standard library plus redis): the worker image carries a copy of this file, because the
worker is the ONLY caller (a user request never reaches a gateway). An empty URL, or a host outside the allow-list,
means "unavailable": zero network call and NO value, default or interpolated. Outbound requests carry exact
allow-listed keys: nothing personal and no exact geometry ever leaves the country.
"""
import datetime as dt
import json as _json
import os
import re
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterable, Mapping
from typing import Any

HORIZON_DAYS = 8
STALE_AFTER = dt.timedelta(hours=24)
CELL_SLOT_SECONDS = 3 * 3600
OUTBOUND_ALLOWLIST: dict[str, frozenset[str]] = {
    "weather": frozenset({"lat", "lon", "days"}),
    "imagery": frozenset({"mgrs", "from", "to"}),
    "push": frozenset({"device_token", "alert_id", "locale"}),
}
_MGRS = re.compile(r"^[0-9]{2}[A-Z]{3}$")
_DAY_KEYS = ("date", "tmin", "tmax", "rain_mm", "wind_kmh", "humidity_pct")
Http = Callable[..., Any]


def assert_outbound(kind: str, payload: Mapping[str, Any]) -> None:
    """The payload carries exactly the allow-listed keys: an extra or a missing key is refused."""
    if set(payload) != OUTBOUND_ALLOWLIST[kind]:
        raise ValueError(f"outbound {kind} payload must carry exactly {sorted(OUTBOUND_ALLOWLIST[kind])}")


def _round_01(value: float) -> float:
    return round(round(value, 1) + 0.0, 1)  # + 0.0 turns -0.0 into 0.0


def build_weather_request(*, lat: float, lon: float) -> dict[str, Any]:
    """A farm position rounded to 0.1 degree (about 11 km): never the exact position."""
    req: dict[str, Any] = {"lat": _round_01(lat), "lon": _round_01(lon), "days": HORIZON_DAYS}
    assert_outbound("weather", req)
    return req


def build_imagery_request(*, mgrs: str, date_from: str, date_to: str) -> dict[str, Any]:
    """Only a public MGRS tile identifier and dates; anything else is refused."""
    if not _MGRS.fullmatch(mgrs or ""):
        raise ValueError("mgrs must be a tile identifier")
    dt.date.fromisoformat(date_from)
    dt.date.fromisoformat(date_to)
    assert_outbound("imagery", {"mgrs": mgrs, "from": date_from, "to": date_to})
    return {"path": f"/tiles/{mgrs}/scenes", "params": {"from": date_from, "to": date_to}}


def build_push_payload(*, device_token: str, alert_id: str, locale: str) -> dict[str, str]:
    payload = {"device_token": device_token, "alert_id": alert_id, "locale": locale}
    assert_outbound("push", payload)
    return payload


def _unavailable(reason: str) -> dict[str, Any]:
    return {"availability": "unavailable", "reason": reason}


def _default_http(method: str, url: str, params: Mapping[str, Any] | None = None, json: Any = None) -> Any:
    full = url + ("?" + urllib.parse.urlencode(params) if params else "")
    data = None if json is None else _json.dumps(json).encode()
    request = urllib.request.Request(full, data=data, method=method, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=10) as response:
        body = response.read()
        return _json.loads(body) if body else {}


class _Gateway:
    def __init__(self, *, url: str, allowed_hosts: Iterable[str], http: Http | None = None) -> None:
        self.url = (url or "").strip()
        self.allowed_hosts = frozenset(h.lower() for h in allowed_hosts)
        self.http: Http = http or _default_http

    def configured(self) -> bool:
        host = (urllib.parse.urlparse(self.url).hostname or "").lower()
        return bool(self.url) and host in self.allowed_hosts


class WeatherGateway(_Gateway):
    def fetch(self, *, lat_r: float, lon_r: float) -> dict[str, Any]:
        """Eight forecast days for a 0.1 degree cell, as the gateway sent them, or an unavailable status with no value."""
        if not self.configured():
            return _unavailable("gateway_not_configured")
        try:
            answer = self.http("GET", self.url, params=build_weather_request(lat=lat_r, lon=lon_r))
            days = answer["days"]
            if not isinstance(days, list) or len(days) != HORIZON_DAYS or not all(
                isinstance(d, dict) and all(k in d for k in _DAY_KEYS) for d in days
            ):
                return _unavailable("gateway_unreachable")
        except (OSError, ValueError, KeyError, TypeError):
            return _unavailable("gateway_unreachable")
        return {"availability": "ok", "days": days}


class ImageryGateway(_Gateway):
    def scenes(self, *, mgrs: str, date_from: str, date_to: str) -> dict[str, Any]:
        if not self.configured():
            return _unavailable("gateway_not_configured")
        req = build_imagery_request(mgrs=mgrs, date_from=date_from, date_to=date_to)
        try:
            answer = self.http("GET", self.url.rstrip("/") + req["path"], params=req["params"])
            scenes = answer["scenes"]
            if not isinstance(scenes, list):
                return _unavailable("gateway_unreachable")
        except (OSError, ValueError, KeyError, TypeError):
            return _unavailable("gateway_unreachable")
        return {"availability": "ok", "scenes": scenes}


class PushGateway(_Gateway):
    def send(self, *, device_token: str, alert_id: str, locale: str) -> dict[str, Any]:
        if not self.configured():
            return _unavailable("gateway_not_configured")
        payload = build_push_payload(device_token=device_token, alert_id=alert_id, locale=locale)
        try:
            self.http("POST", self.url, json=payload)
        except (OSError, ValueError):
            return _unavailable("gateway_unreachable")
        return {"availability": "ok"}


def weather_freshness(fetched_at: dt.datetime | None, now: dt.datetime) -> dict[str, Any]:
    """`ok` up to 24 h old, then `stale`; never fetched = unavailable with no value."""
    if fetched_at is None:
        return _unavailable("gateway_not_configured")
    if now - fetched_at > STALE_AFTER:
        return {"availability": "stale", "reason": "stale"}
    return {"availability": "ok", "reason": None}


def _redis() -> Any:
    import redis.asyncio as redis

    return redis.from_url(os.environ.get("AYLAL_REDIS_URL", "redis://redis:6379/0"))  # type: ignore[no-untyped-call]


async def acquire_cell_slot(cell_id: str, now: dt.datetime) -> bool:
    """One call per 0.1 degree cell and per 3 hours (Redis lock); False when the slot is already taken."""
    slot = int(now.timestamp()) // CELL_SLOT_SECONDS
    client = _redis()
    try:
        return bool(await client.set(f"gw:weather:cell:{cell_id}:{slot}", "1", nx=True, ex=CELL_SLOT_SECONDS))
    finally:
        await client.aclose()


async def acquire_daily_budget(kind: str, limit: int, day: dt.date) -> bool:
    """Global daily call budget per gateway kind."""
    client = _redis()
    try:
        key = f"gw:budget:{kind}:{day.isoformat()}"
        used = int(await client.incr(key))
        await client.expire(key, 2 * 86400)
        return used <= limit
    finally:
        await client.aclose()
