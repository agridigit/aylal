import { availableOffline, offlineRegionFor, tileSource } from "../offlineRegion";

const BASE = "https://tiles.aylal.example.ma";
const geom = (lon: number, lat: number) => ({ type: "Polygon", coordinates: [[[lon, lat], [lon + 0.01, lat], [lon + 0.01, lat + 0.01], [lon, lat + 0.01], [lon, lat]]] });
const rows = [
  { id: "a", name: "A", geometry: JSON.stringify(geom(-7.6, 33.57)), status_summary: "ok", archived_at: null },
  { id: "b", name: "B", geometry: JSON.stringify(geom(-7.5, 33.6)), status_summary: null, archived_at: null },
];

describe("offline map (R4-A4) and Moroccan tile hosting", () => {
  it("given already loaded parcels when offline then they are all available without any network call", async () => {
    const fetchSpy = jest.fn();
    (globalThis as { fetch?: unknown }).fetch = fetchSpy;
    expect(availableOffline(rows).map((f) => f.properties.id)).toEqual(["a", "b"]);
    expect(fetchSpy).not.toHaveBeenCalled();
  });
  it("given the configured base url when building the tile source then the only host is AYLAL_TILES_BASE_URL", () => {
    const src = tileSource(BASE);
    expect(src.url).toBe(`pmtiles://${BASE}/morocco.pmtiles`);
    expect(new URL(src.url.replace("pmtiles://", "")).host).toBe("tiles.aylal.example.ma");
  });
  it("given no base url or a non https one when building the tile source then it throws tiles_base_url_missing", () => {
    expect(() => tileSource("")).toThrow("tiles_base_url_missing");
    expect(() => tileSource("http://insecure.example")).toThrow("tiles_base_url_missing");
  });
  it("given the farm parcels when planning the offline region then its bounds cover every parcel with a margin and no foreign url appears", () => {
    const region = offlineRegionFor(rows, BASE);
    const [w, s, e, n] = region.bounds;
    expect(w).toBeLessThan(-7.6);
    expect(e).toBeGreaterThan(-7.49);
    expect(s).toBeLessThan(33.57);
    expect(n).toBeGreaterThan(33.61);
    expect(JSON.stringify(region)).not.toMatch(/openstreetmap|mapbox|googleapis|maptiler|arcgis|bing/i);
    expect(region.source.url.startsWith(`pmtiles://${BASE}`)).toBe(true);
  });
  it("given no parcel when planning the offline region then it covers the national extent", () => {
    const [w, s, e, n] = offlineRegionFor([], BASE).bounds;
    expect([w, s, e, n]).toEqual([-17.2, 20.7, -0.9, 36.0]);
  });
});
