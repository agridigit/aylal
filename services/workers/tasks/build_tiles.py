"""Build the Morocco PMTiles archive; published only under AYLAL_TILES_BASE_URL (hosted in Morocco)."""
import asyncio
import os
from typing import Any

TILES_FILE = "morocco.pmtiles"


class TilesBaseUrlMissing(Exception):
    """AYLAL_TILES_BASE_URL is empty or not https: no tiles are built or referenced."""


def tiles_url(base_url: str) -> str:
    base = (base_url or "").strip()
    if not base.startswith("https://") or len(base) <= len("https://"):
        raise TilesBaseUrlMissing("AYLAL_TILES_BASE_URL must be an https URL")
    return f"{base.rstrip('/')}/{TILES_FILE}"


async def _tippecanoe(source: str, output: str) -> str:
    proc = await asyncio.create_subprocess_exec("tippecanoe", "-o", output, "--force", source)
    if await proc.wait() != 0:
        raise RuntimeError("tile build failed")
    return output


async def build_tiles(ctx: dict[str, Any], source: str) -> dict[str, Any]:
    url = tiles_url(ctx.get("tiles_base_url", os.environ.get("AYLAL_TILES_BASE_URL", "")))
    runner = ctx.get("runner", _tippecanoe)
    await runner(source, f"{ctx.get('output_dir', '/tmp')}/{TILES_FILE}")
    return {"url": url, "built": True}
