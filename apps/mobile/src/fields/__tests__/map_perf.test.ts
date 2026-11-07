import { buildFieldsGeoJson } from "../mapData";

// SC-004 (initial threshold): 50 parcels rendered in under 2 s. Measured value goes in the acceptance template.
const geom = (i: number) => JSON.stringify({ type: "Polygon", coordinates: [[[-7.6 + i * 0.002, 33.57], [-7.599 + i * 0.002, 33.57], [-7.599 + i * 0.002, 33.571], [-7.6 + i * 0.002, 33.571], [-7.6 + i * 0.002, 33.57]]] });

describe("map performance (R4-A1, SC-004)", () => {
  it("given a farm of 50 parcels when building the map data then all 50 features are produced in under 2 seconds", () => {
    const rows = Array.from({ length: 50 }, (_, i) => ({ id: `f${i}`, name: `F${i}`, geometry: geom(i), status_summary: ["ok", "watch", "act", null][i % 4]!, archived_at: null }));
    const t0 = Date.now();
    const fc = buildFieldsGeoJson(rows);
    expect(Date.now() - t0).toBeLessThan(2000);
    expect(fc.features).toHaveLength(50);
  });
});
