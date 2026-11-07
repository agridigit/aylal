#!/bin/sh
# Builds the Morocco PMTiles archive locally (no third-party service). Run through `make tiles`.
# Input: a Morocco vector source (GeoJSONL) supplied by the operator in $AYLAL_TILES_SOURCE.
# Output: $AYLAL_TILES_OUT/morocco.pmtiles, to be uploaded to the Moroccan host served as AYLAL_TILES_BASE_URL.
set -eu
: "${AYLAL_TILES_SOURCE:?AYLAL_TILES_SOURCE (local GeoJSONL of Morocco) is required}"
: "${AYLAL_TILES_BASE_URL:?AYLAL_TILES_BASE_URL (https, hosted in Morocco) is required}"
case "$AYLAL_TILES_BASE_URL" in "https:"//*) ;; *) echo "AYLAL_TILES_BASE_URL must be https" >&2; exit 1 ;; esac
OUT="${AYLAL_TILES_OUT:-/out}"
mkdir -p "$OUT"
tippecanoe -o "$OUT/morocco.pmtiles" --force "$AYLAL_TILES_SOURCE"
echo "built $OUT/morocco.pmtiles -> publish under $AYLAL_TILES_BASE_URL/morocco.pmtiles"
