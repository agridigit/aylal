import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { buildMapStyle } from "../mapStyle";

const BASE = "https://tiles.aylal.example.ma";
const FOREIGN = /(openstreetmap|mapbox|maptiler|googleapis|google\.com\/maps|bing\.com|carto|stadiamaps|nominatim|arcgis|tomtom|protomaps\.com)/i;

describe("map style allowlist (Morocco guard)", () => {
  it("given the base url when building the style then every URL it references is under AYLAL_TILES_BASE_URL", () => {
    const urls = JSON.stringify(buildMapStyle(BASE)).match(/(?:pmtiles:\/\/)?https?:\/\/[^"]+/g) ?? [];
    expect(urls.length).toBeGreaterThan(0);
    for (const u of urls) expect(u.replace("pmtiles://", "").startsWith(BASE)).toBe(true);
  });
  it("given no https base url when building the style then it throws tiles_base_url_missing", () => {
    expect(() => buildMapStyle("")).toThrow("tiles_base_url_missing");
  });
  it("given the F2 mobile sources then none references a third-party tile or geocoding domain", () => {
    const dir = join(__dirname, "..");
    for (const f of readdirSync(dir).filter((n) => n.endsWith(".ts"))) expect(readFileSync(join(dir, f), "utf8")).not.toMatch(FOREIGN);
  });
});
