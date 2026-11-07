import { MOROCCO_EXTENT } from "@aylal/domain/geometry";
import { buildFieldsGeoJson } from "./mapData";
import type { FieldRow } from "./mapData";

/** The only tile host is AYLAL_TILES_BASE_URL (hosted in Morocco); no third-party default. */
export function tileSource(baseUrl: string): { type: "vector"; url: string } {
  const base = (baseUrl ?? "").trim();
  if (!base.startsWith("https://") || base.length <= "https://".length) throw new Error("tiles_base_url_missing");
  return { type: "vector", url: `pmtiles://${base.replace(/\/+$/, "")}/morocco.pmtiles` };
}

/** Parcels already loaded locally are available without any network call. */
export function availableOffline(rows: readonly FieldRow[]) {
  return buildFieldsGeoJson(rows).features;
}

const MARGIN_DEG = 0.02;

function coords(g: any, out: [number, number][]) {
  if (Array.isArray(g) && typeof g[0] === "number") out.push([g[0], g[1]]);
  else if (Array.isArray(g)) for (const c of g) coords(c, out);
}

export function offlineRegionFor(rows: readonly FieldRow[], baseUrl: string) {
  const source = tileSource(baseUrl);
  const pts: [number, number][] = [];
  for (const f of availableOffline(rows)) coords((f.geometry as { coordinates?: unknown }).coordinates, pts);
  const e = MOROCCO_EXTENT;
  const bounds: [number, number, number, number] = pts.length
    ? [
        Math.min(...pts.map((p) => p[0])) - MARGIN_DEG,
        Math.min(...pts.map((p) => p[1])) - MARGIN_DEG,
        Math.max(...pts.map((p) => p[0])) + MARGIN_DEG,
        Math.max(...pts.map((p) => p[1])) + MARGIN_DEG,
      ]
    : [e.minLon, e.minLat, e.maxLon, e.maxLat];
  return { bounds, source };
}
