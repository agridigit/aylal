"""T036 (contract part) - crop and season routes conform to specs/003-fields-crops/contracts/openapi.yaml.
The packages/ui component tests of T036 are blocked by T004 (see decisions.md)."""
import os
import re
from pathlib import Path

from tests.helpers import auth
from tests.integration._f2 import add_field, new_user

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
CROP_KEYS = {"id", "farm_id", "slug", "name_ary", "name_ar", "name_fr", "cycle", "photo_key", "varieties", "stages", "has_agronomy", "validated"}
SEASON_KEYS = {"id", "field_id", "crop_id", "variety", "planting_year", "sowing_date", "started_at", "ended_at",
               "stage_estimated", "stage_corrected", "stage_corrected_at", "destination"}


def test_given_the_contract_when_comparing_then_every_crop_and_season_route_and_method_exists(client):
    live = client.get("/openapi.json").json()["paths"]
    for path, methods in PATHS.items():
        if "/crops" in path or "/seasons" in path:
            assert path in live and set(methods) <= set(live[path]), path


def test_given_the_reference_list_then_every_crop_has_the_documented_shape_and_a_photo(client, make_farm, token_for):
    owner = new_user()
    r = client.get("/v1/crops", headers=auth(token_for(owner)))
    assert r.status_code == 200 and len(r.json()["items"]) == 16
    for c in r.json()["items"]:
        assert CROP_KEYS <= set(c) and c["photo_key"], c["slug"]


def test_given_a_season_creation_then_it_returns_the_documented_statuses(client, make_farm, token_for):
    owner = new_user()
    farm = make_farm({owner: "owner"})
    h = auth(token_for(owner))
    field = add_field(farm)
    crop = next(c for c in client.get("/v1/crops", headers=h).json()["items"] if c["slug"] == "durum-wheat")
    base = f"/v1/farms/{farm}/fields/{field}/seasons"
    assert {"201", "403", "404", "409", "422"} <= PATHS["/v1/farms/{farm_id}/fields/{field_id}/seasons"]["post"]["responses"]
    body = {"crop_id": crop["id"], "sowing_date": "2026-01-01", "started_at": "2026-01-01"}
    r = client.post(base, json=body, headers=h)
    assert r.status_code == 201 and SEASON_KEYS <= set(r.json())
    assert client.post(base, json=body, headers=h).status_code == 409
    assert client.post(base, json={**body, "sowing_date": "bad"}, headers=h).status_code in (409, 422)
