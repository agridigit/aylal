"""T054 (worker part) - PMTiles are built then published ONLY under AYLAL_TILES_BASE_URL (hosted in Morocco)."""
import asyncio

import pytest
from tasks.build_tiles import TilesBaseUrlMissing, build_tiles, tiles_url

BASE = "https://tiles.aylal.example.ma"


class FakeRunner:
    def __init__(self):
        self.calls = []

    async def __call__(self, source, output):
        self.calls.append((source, output))
        return output


def test_given_a_base_url_when_computing_the_tiles_url_then_it_points_to_morocco_pmtiles_under_that_host_only():
    assert tiles_url(BASE) == f"{BASE}/morocco.pmtiles"
    assert tiles_url(BASE + "/") == f"{BASE}/morocco.pmtiles"


@pytest.mark.parametrize("bad", ["", "   ", "http://insecure.example"])
def test_given_no_or_a_non_https_base_url_when_computing_the_tiles_url_then_it_is_refused(bad):
    with pytest.raises(TilesBaseUrlMissing):
        tiles_url(bad)


def test_given_a_source_when_the_task_runs_then_the_runner_writes_a_pmtiles_file_and_the_result_carries_the_hosted_url():
    runner = FakeRunner()
    res = asyncio.run(build_tiles({"runner": runner, "tiles_base_url": BASE}, source="/data/morocco.geojson"))
    assert runner.calls and runner.calls[0][1].endswith("morocco.pmtiles")
    assert res == {"url": f"{BASE}/morocco.pmtiles", "built": True}


def test_given_no_base_url_when_the_task_runs_then_nothing_is_built():
    runner = FakeRunner()
    with pytest.raises(TilesBaseUrlMissing):
        asyncio.run(build_tiles({"runner": runner, "tiles_base_url": ""}, source="/data/morocco.geojson"))
    assert runner.calls == []


def test_given_the_worker_settings_then_build_tiles_is_registered():
    import worker

    names = {getattr(f, "__name__", getattr(f, "name", "")) for f in worker.WorkerSettings.functions}
    assert "build_tiles" in names
