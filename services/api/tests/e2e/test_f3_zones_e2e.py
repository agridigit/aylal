"""T064 - R4-A1..A3 on the running stack: a zone is served with its outline; the worker records an observation with an opaque photo id and the zone becomes visited.

Zone creation from rasters needs the imagery gateway, absent on the stack: it is covered by services/workers/tests/test_detect_zones.py (injected grids).
"""
import uuid

import pytest

from tests.e2e._f3 import client, setup_farm
from tests.integration._f3 import seed_zone

JPEG = b"\xff\xd8\xff\xe0" + b"0" * 512


@pytest.fixture(scope="module")
def farm():
    with client() as c:
        yield setup_farm(c, 3, worker=True, hidden=1)  # one worker login for the file (OTP limiter is per IP)


def test_given_a_zone_to_check_when_the_worker_goes_there_and_records_an_observation_with_a_photo_then_the_zone_becomes_visited(farm):
    with client() as c:
        s = farm
        farm, parcel = s["farm"], s["parcels"][0]
        zone = seed_zone(uuid.UUID(farm), uuid.UUID(parcel))
        listed = {z["id"]: z for z in c.get(f"/farms/{farm}/zones", headers=s["wh"]).json()}
        assert listed[str(zone)]["status"] == "open" and listed[str(zone)]["geometry"]["type"] == "Polygon" and listed[str(zone)]["centroid"]["type"] == "Point"
        photo = c.post(f"/farms/{farm}/zones/{zone}/observations/photo", files={"photo": ("p.jpg", JPEG, "image/jpeg")}, headers=s["wh"])
        assert photo.status_code == 201, photo.text
        obs = c.post(f"/farms/{farm}/zones/{zone}/observations", json={"id": str(uuid.uuid4()), "note": "feuilles jaunes", "photo_id": photo.json()["photo_id"]}, headers=s["wh"])
        assert obs.status_code == 201, obs.text
        after = {z["id"]: z for z in c.get(f"/farms/{farm}/zones", headers=s["wh"]).json()}
        assert after[str(zone)]["status"] == "visited"
        assert "farms/" not in obs.text and "photo_key" not in obs.text


def test_given_a_zone_when_the_worker_tries_to_dismiss_it_then_403_and_the_owner_dismisses_it(farm):
    with client() as c:
        s = farm
        zone = seed_zone(uuid.UUID(s["farm"]), uuid.UUID(s["parcels"][1]))
        assert c.post(f"/farms/{s['farm']}/zones/{zone}/dismiss", headers=s["wh"]).status_code == 403
        assert c.post(f"/farms/{s['farm']}/zones/{zone}/dismiss", headers=s["oh"]).json()["status"] == "dismissed"


def test_given_a_zone_of_a_parcel_not_assigned_when_the_worker_observes_then_404(farm):
    with client() as c:
        s = farm
        zone = seed_zone(uuid.UUID(s["farm"]), uuid.UUID(s["parcels"][2]))
        r = c.post(f"/farms/{s['farm']}/zones/{zone}/observations", json={"id": str(uuid.uuid4()), "note": "x"}, headers=s["wh"])
        assert r.status_code == 404 and r.json() == {"detail": "not_found"}
