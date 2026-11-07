"""T025 - field routes conform to specs/003-fields-crops/contracts/openapi.yaml and geometry-rules.md."""
import os
import re
from pathlib import Path

from tests.helpers import auth
from tests.integration._f2 import new_user, square

SPEC = Path(os.environ.get("AYLAL_REPO_DIR", "/repo")) / "specs/003-fields-crops/contracts/openapi.yaml"

def _paths() -> dict[str, dict]:
    """openapi.yaml of F2 is not valid YAML yet (unquoted '?' in a flow mapping, fixed by T019): read it line by line."""
    out: dict[str, dict] = {}
    for line in SPEC.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^  (/v1/\S+): (.*)$", line)
        if m:
            methods = re.findall(r"(?:\{|\},)\s*(get|post|patch|delete|put): \{ summary", m.group(2))
            out[m.group(1)] = {meth: {"responses": set(re.findall(r'"(\d{3})":', m.group(2)))} for meth in methods}
    return out


PATHS = _paths()
FIELD_KEYS = {"id", "farm_id", "name", "geometry", "area_calc_ha", "area_declared_ha", "irrigation", "greenhouse", "soil",
              "source", "gps_accuracy_m", "status_summary", "archived_at", "server_version"}


def test_given_the_contract_when_comparing_with_the_running_api_then_every_field_route_and_method_exists(client):
    live = client.get("/openapi.json").json()["paths"]
    for path, methods in PATHS.items():
        if "/fields" not in path:
            continue
        assert path in live, path
        assert set(methods) <= set(live[path]), (path, set(methods) - set(live[path]))


def test_given_a_creation_then_it_returns_the_documented_201_with_warnings_and_422_codes(client, make_farm, token_for):
    owner = new_user()
    farm = make_farm({owner: "owner"})
    h = auth(token_for(owner))
    post = PATHS["/v1/farms/{farm_id}/fields"]["post"]["responses"]
    assert {"201", "403", "404", "422"} <= set(post)
    r = client.post(f"/v1/farms/{farm}/fields", json={"name": "A", "geometry": square(), "irrigation": "drip", "greenhouse": False}, headers=h)
    assert r.status_code == 201 and FIELD_KEYS <= set(r.json()) and r.json()["warnings"] == []
    assert client.post(f"/v1/farms/{farm}/fields", json={"name": "A"}, headers=h).status_code == 422
    assert client.post(f"/v1/farms/{farm}/fields", json={"name": "P", "geometry": square(2.35, 48.85)}, headers=h).status_code == 422


def test_given_geometry_rules_when_creating_then_every_documented_rejection_is_a_422(client, make_farm, token_for):
    owner = new_user()
    farm = make_farm({owner: "owner"})
    h = auth(token_for(owner))
    bad = [
        {"type": "Point", "coordinates": [-7.6, 33.57]},
        {"type": "Polygon", "coordinates": [[[-7.6, 33.57], [-7.59, 33.57], [-7.6, 33.57]]]},
        {"type": "Polygon", "coordinates": [[[-7.6, 33.57], [float("nan"), 1], [-7.5, 33.6], [-7.6, 33.57]]]},
    ]
    for g in bad:
        try:
            r = client.post(f"/v1/farms/{farm}/fields", json={"name": "B", "geometry": g}, headers=h)
        except ValueError:  # NaN is not JSON-serialisable: the client cannot even send it
            continue
        assert r.status_code == 422, g


def test_given_the_delete_and_restore_routes_then_they_match_the_documented_statuses(client, make_farm, token_for):
    owner = new_user()
    farm = make_farm({owner: "owner"})
    h = auth(token_for(owner))
    fid = client.post(f"/v1/farms/{farm}/fields", json={"name": "A", "geometry": square()}, headers=h).json()["id"]
    assert "204" in PATHS["/v1/farms/{farm_id}/fields/{field_id}"]["delete"]["responses"]
    assert client.delete(f"/v1/farms/{farm}/fields/{fid}", headers=h).status_code == 204
    assert client.post(f"/v1/farms/{farm}/fields/{fid}/restore", headers=h).status_code == 200
