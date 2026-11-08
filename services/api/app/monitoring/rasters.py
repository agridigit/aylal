"""Raster reading with a size cap applied BEFORE any decoding (G4). Only the worker reads rasters in production."""
import importlib
from typing import Any

from app.domain.monitoring_limits import LIMITS


class RasterTooLarge(ValueError):
    pass


def read_raster(data: bytes) -> Any:
    """First band of a raster as an array. Refused above 500 MB without decoding anything."""
    if len(data) > LIMITS["raster_bytes"]:
        raise RasterTooLarge("raster exceeds the cap")
    rasterio = importlib.import_module("rasterio")
    with rasterio.MemoryFile(data) as mem, mem.open() as ds:
        return ds.read(1)
