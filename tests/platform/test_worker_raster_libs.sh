#!/usr/bin/env bash
# F3 defect 4 - the worker image can import the raster stack (rasterio needs the system libraries of GDAL's runtime, e.g. libexpat):
# without it every raster read of the imagery tasks fails at import time.
source "$(dirname "$0")/lib.sh"

out="$(bash scripts/dc.sh --profile test run --rm --no-deps worker python -c 'import rasterio, shapely, numpy' 2>&1)"; rc=$?
if [ $rc -ne 0 ]; then
  echo "$out" | tail -n 5
  fail "the worker image cannot import rasterio, shapely and numpy"
fi
out="$(bash scripts/dc.sh --profile test run --rm --no-deps worker python -c '
import numpy, rasterio
from rasterio.io import MemoryFile
from rasterio.transform import from_origin
a = numpy.arange(4, dtype="float32").reshape(2, 2)
with MemoryFile() as m:
    with m.open(driver="GTiff", width=2, height=2, count=1, dtype="float32", transform=from_origin(0, 2, 1, 1)) as w:
        w.write(a, 1)
    with m.open() as r:
        assert r.read(1).sum() == 6.0
' 2>&1)"; rc=$?
[ $rc -eq 0 ] || { echo "$out" | tail -n 5; fail "the worker image cannot write and read a GeoTIFF in memory"; }
finish
