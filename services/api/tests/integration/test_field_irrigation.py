"""T045 - irrigation mode and greenhouse stored and read back on create and update (R3-A1, R3-A2)."""
import pytest

from tests.helpers import auth
from tests.integration._f2 import new_user, square

MODES = ["rainfed", "gravity", "sprinkler", "drip", "pivot"]


@pytest.fixture
def ctx(make_farm, token_for):
    owner = new_user()
    farm = make_farm({owner: "owner"})
    return dict(base=f"/v1/farms/{farm}/fields", h=auth(token_for(owner)))


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("greenhouse", [True, False])
def test_given_each_irrigation_mode_with_and_without_greenhouse_when_creating_then_both_are_saved_and_read_back(client, ctx, mode, greenhouse):
    r = client.post(ctx["base"], json={"name": "A", "geometry": square(), "irrigation": mode, "greenhouse": greenhouse}, headers=ctx["h"])
    assert r.status_code == 201, r.text
    got = client.get(f"{ctx['base']}/{r.json()['id']}", headers=ctx["h"]).json()
    assert (got["irrigation"], got["greenhouse"]) == (mode, greenhouse)


def test_given_a_field_without_irrigation_when_creating_then_irrigation_is_null_and_greenhouse_false(client, ctx):
    got = client.post(ctx["base"], json={"name": "A", "geometry": square()}, headers=ctx["h"]).json()
    assert got["irrigation"] is None and got["greenhouse"] is False


@pytest.mark.parametrize("mode", MODES)
def test_given_a_field_when_modifying_its_irrigation_and_greenhouse_then_the_new_values_are_read_back(client, ctx, mode):
    fid = client.post(ctx["base"], json={"name": "A", "geometry": square(), "irrigation": "rainfed"}, headers=ctx["h"]).json()["id"]
    r = client.patch(f"{ctx['base']}/{fid}", json={"irrigation": mode, "greenhouse": True}, headers=ctx["h"])
    assert r.status_code == 200
    got = client.get(f"{ctx['base']}/{fid}", headers=ctx["h"]).json()
    assert (got["irrigation"], got["greenhouse"]) == (mode, True)


def test_given_an_unknown_irrigation_mode_when_creating_or_modifying_then_422_and_the_field_is_unchanged(client, ctx):
    assert client.post(ctx["base"], json={"name": "A", "geometry": square(), "irrigation": "flood"}, headers=ctx["h"]).status_code == 422
    fid = client.post(ctx["base"], json={"name": "A", "geometry": square(), "irrigation": "drip"}, headers=ctx["h"]).json()["id"]
    assert client.patch(f"{ctx['base']}/{fid}", json={"irrigation": "flood"}, headers=ctx["h"]).status_code == 422
    assert client.get(f"{ctx['base']}/{fid}", headers=ctx["h"]).json()["irrigation"] == "drip"


def test_given_a_non_boolean_greenhouse_when_creating_then_422(client, ctx):
    assert client.post(ctx["base"], json={"name": "A", "geometry": square(), "greenhouse": "yes"}, headers=ctx["h"]).status_code == 422
