"""T020 / T054 - Morocco guard: tiles come only from AYLAL_TILES_BASE_URL; no third-party tile or geocoding domain anywhere."""
import os
import re
from pathlib import Path

REPO = Path(os.environ.get("AYLAL_REPO_DIR", "/repo"))
FOREIGN = re.compile(
    r"(openstreetmap|tile\.osm|mapbox|maptiler|googleapis|google\.com/maps|bing\.com|here\.com|carto(cdn|\.com)|stadiamaps|nominatim|arcgis|tomtom|protomaps\.com)",
    re.I,
)
ROOTS = ["services/api/app", "services/workers/tasks", "apps/mobile/src/fields", "apps/mobile/src/screens/Map", "infra/tiles"]


def _files():
    for root in ROOTS:
        base = REPO / root
        if not base.exists():
            continue
        for p in base.rglob("*"):
            if p.is_file() and p.suffix in {".py", ".ts", ".tsx", ".json", ".sh", ".yaml", ".yml", ".md"} and "__tests__" not in p.parts:
                yield p


def test_given_the_map_code_and_infra_then_no_foreign_tile_or_geocoding_domain_is_referenced():
    bad = [str(p.relative_to(REPO)) for p in _files() if FOREIGN.search(p.read_text(encoding="utf-8", errors="ignore"))]
    assert bad == []


def test_given_the_tiles_infra_then_it_builds_pmtiles_locally_and_hosts_no_external_default():
    d = REPO / "infra/tiles"
    assert d.is_dir(), "infra/tiles missing"
    text = "\n".join(p.read_text(encoding="utf-8") for p in d.rglob("*") if p.is_file())
    assert "pmtiles" in text.lower() and "AYLAL_TILES_BASE_URL" in text
    assert not re.search(r"https?://(?!\$|localhost)", text.replace("https://${", "")), "no hard-coded external URL"


def test_given_the_makefile_then_a_tiles_target_exists():
    assert re.search(r"^tiles:", (REPO / "Makefile").read_text(encoding="utf-8"), re.M)
