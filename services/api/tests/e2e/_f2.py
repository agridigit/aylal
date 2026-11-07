"""Shared helpers for the F2 e2e tests (running stack through the proxy, test OTP 000000)."""
import httpx

from tests.helpers import sql

BASE = "https://proxy/v1"
CASA = {"lat": 33.5731, "lon": -7.5898}


def square(lon: float = -7.60, lat: float = 33.57, size: float = 0.002) -> dict:
    return {"type": "Polygon", "coordinates": [[[lon, lat], [lon + size, lat], [lon + size, lat + size], [lon, lat + size], [lon, lat]]]}


def fresh(phone: str) -> None:
    sql("DELETE FROM otp_challenges WHERE phone_e164=$1", phone)
    sql("DELETE FROM farms WHERE owner_id IN (SELECT id FROM users WHERE phone_e164=$1)", phone)
    for t in ("consents", "refresh_tokens"):
        sql(f"DELETE FROM {t} WHERE user_id IN (SELECT id FROM users WHERE phone_e164=$1)", phone)
    sql("DELETE FROM farm_members WHERE user_id IN (SELECT id FROM users WHERE phone_e164=$1)", phone)
    sql("DELETE FROM users WHERE phone_e164=$1", phone)


def owner_with_farm(c: httpx.Client, phone: str) -> tuple[dict, str]:
    assert c.post("/auth/otp/request", json={"phone": phone}).status_code == 202
    s = c.post("/auth/otp/verify", json={"phone": phone, "code": "000000"}).json()
    h = {"Authorization": f"Bearer {s['access_token']}"}
    farm = c.post("/farms", json={"name": "Atlas", "location": CASA}, headers=h).json()["id"]
    return h, farm
