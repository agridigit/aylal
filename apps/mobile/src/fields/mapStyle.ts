import { tileSource } from "./offlineRegion";

/** Map style: the only remote host is AYLAL_TILES_BASE_URL (hosted in Morocco); no third-party tiles, glyphs or geocoding. */
export function buildMapStyle(baseUrl: string) {
  const src = tileSource(baseUrl);
  const base = src.url.replace("pmtiles://", "").replace(/\/morocco\.pmtiles$/, "");
  return {
    version: 8 as const,
    sources: { morocco: src, fields: { type: "geojson" as const, data: { type: "FeatureCollection", features: [] } } },
    glyphs: `${base}/fonts/{fontstack}/{range}.pbf`,
    layers: [
      { id: "background", type: "background", paint: { "background-color": "#F4F1EA" } },
      { id: "fields-fill", type: "fill", source: "fields", paint: { "fill-color": ["get", "color"], "fill-opacity": 0.55 } },
      { id: "fields-line", type: "line", source: "fields", paint: { "line-color": ["get", "color"], "line-width": 2 } },
    ],
  };
}
