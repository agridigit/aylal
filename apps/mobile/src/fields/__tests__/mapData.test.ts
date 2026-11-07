import { FIELDS_LOCAL_SQL, STATUS_COLORS, buildFieldsGeoJson } from "../mapData";

// Contract (GREEN): rows are parcels rows read from local SQLite (geometry stored as a JSON string).
const geom = (lon: number) => JSON.stringify({ type: "Polygon", coordinates: [[[lon, 33.57], [lon + 0.001, 33.57], [lon + 0.001, 33.571], [lon, 33.571], [lon, 33.57]]] });
const row = (id: string, status: string | null, extra: Record<string, unknown> = {}) =>
  ({ id, name: `Field ${id}`, geometry: geom(-7.6), status_summary: status, archived_at: null, ...extra });

describe("map data from local parcels (R4-A1, R4-A2)", () => {
  it("given fields with ok, watch and act when building the collection then each feature carries its status colour", () => {
    const fc = buildFieldsGeoJson([row("a", "ok"), row("b", "watch"), row("c", "act")]);
    expect(fc.type).toBe("FeatureCollection");
    expect(fc.features.map((f) => f.properties.color)).toEqual([STATUS_COLORS.ok, STATUS_COLORS.watch, STATUS_COLORS.act]);
    expect(fc.features.map((f) => f.properties.id)).toEqual(["a", "b", "c"]);
  });
  it("given a field whose status is not computed yet when building then it gets a neutral colour distinct from the three states", () => {
    const [f] = buildFieldsGeoJson([row("a", null)]).features;
    expect(f!.properties.status).toBe("unknown");
    expect(f!.properties.color).toBe(STATUS_COLORS.unknown);
    expect([STATUS_COLORS.ok, STATUS_COLORS.watch, STATUS_COLORS.act]).not.toContain(STATUS_COLORS.unknown);
  });
  it("given an unexpected status value when building then it falls back to the neutral colour", () => {
    expect(buildFieldsGeoJson([row("a", "banana")]).features[0]!.properties.color).toBe(STATUS_COLORS.unknown);
  });
  it("given an archived field or an invalid geometry when building then it is left out, the others stay", () => {
    const fc = buildFieldsGeoJson([row("a", "ok"), row("b", "ok", { archived_at: "2026-01-01" }), row("c", "ok", { geometry: "not json" })]);
    expect(fc.features.map((f) => f.properties.id)).toEqual(["a"]);
  });
  it("given a geometry already parsed as an object when building then it is accepted", () => {
    expect(buildFieldsGeoJson([row("a", "ok", { geometry: JSON.parse(geom(-7.6)) })]).features).toHaveLength(1);
  });
  it("given the map query then it reads the local parcels table only, with no join nor sub-query (PowerSync constraint)", () => {
    expect(FIELDS_LOCAL_SQL).toMatch(/FROM parcels/i);
    expect(FIELDS_LOCAL_SQL).not.toMatch(/\bJOIN\b|\(\s*SELECT/i);
  });
});
