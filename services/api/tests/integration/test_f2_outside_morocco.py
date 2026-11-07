"""T020 (garde-fou n°6) - a field outside Morocco is refused with 422 outside_morocco, on REST and on sync."""
import pytest

from tests.helpers import auth, sql
from tests.integration._f2 import new_user, square


@pytest.fixture
def ctx(make_farm, token_for):
    owner = new_user()
    farm = make_farm({owner: "owner"})
    return dict(farm=farm, h=auth(token_for(owner)))


@pytest.mark.parametrize("lon,lat", [(2.35, 48.85), (-3.7, 40.4), (-7.6, 20.0)])
def test_given_a_polygon_outside_morocco_when_creating_then_422_and_nothing_stored(client, ctx, lon, lat):
    r = client.post(f"/v1/farms/{ctx['farm']}/fields", json={"name": "X", "geometry": square(lon, lat)}, headers=ctx["h"])
    assert r.status_code == 422 and "outside_morocco" in r.text
    assert sql("SELECT count(*) FROM parcels WHERE farm_id=$1", ctx["farm"])[0][0] == 0
