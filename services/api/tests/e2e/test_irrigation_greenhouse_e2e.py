"""T046 - five irrigation modes with and without greenhouse on the running stack (R3-A1, R3-A2)."""
import httpx

from tests.e2e._f2 import BASE, fresh, owner_with_farm, square

PHONE = "+212677006603"
MODES = ["rainfed", "gravity", "sprinkler", "drip", "pivot"]


def test_given_each_irrigation_mode_with_and_without_greenhouse_when_saved_then_the_field_card_shows_them() -> None:
    fresh(PHONE)
    with httpx.Client(base_url=BASE, verify=False, timeout=60) as c:
        h, farm = owner_with_farm(c, PHONE)
        for i, mode in enumerate(MODES):
            for j, greenhouse in enumerate((False, True)):
                body = {"name": f"{mode}-{greenhouse}", "geometry": square(-7.9 + (i * 2 + j) * 0.004), "irrigation": mode, "greenhouse": greenhouse}
                f = c.post(f"/farms/{farm}/fields", json=body, headers=h)
                assert f.status_code == 201, f.text
                card = c.get(f"/farms/{farm}/fields/{f.json()['id']}", headers=h).json()
                assert (card["irrigation"], card["greenhouse"]) == (mode, greenhouse)
        f = c.post(f"/farms/{farm}/fields", json={"name": "Edit", "geometry": square(-7.3)}, headers=h).json()
        r = c.patch(f"/farms/{farm}/fields/{f['id']}", json={"irrigation": "pivot", "greenhouse": True}, headers=h)
        assert r.status_code == 200 and (r.json()["irrigation"], r.json()["greenhouse"]) == ("pivot", True)
        assert c.post(f"/farms/{farm}/fields", json={"name": "Bad", "geometry": square(-7.2), "irrigation": "flood"}, headers=h).status_code == 422
    fresh(PHONE)
