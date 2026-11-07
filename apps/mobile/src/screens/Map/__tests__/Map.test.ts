import { buildMapViewModel } from "../mapViewModel";

const parcels = (n: number) =>
  Array.from({ length: n }, (_, i) => ({
    id: `p${i}`,
    name: `Plot ${i}`,
    geometry: { type: "Polygon" as const, coordinates: [[[0, 0], [0, 1], [1, 1], [0, 0]]] },
    vigor: (i % 10) / 10,
  }));

describe("Map from local cache (AC6.2, FR-027)", () => {
  it("Given 50 cached parcels with vigor and no network, When the map is built, Then 50 features are rendered with their vigor", () => {
    const vm = buildMapViewModel({ parcels: parcels(50), online: false });
    expect(vm.state).toBe("ready");
    expect(vm.features).toHaveLength(50);
    expect(vm.features[3].properties.vigor).toBeCloseTo(0.3);
  });

  it("Given no network, When the map is built, Then tiles and fonts come from local files and no request is needed", () => {
    const vm = buildMapViewModel({ parcels: parcels(50), online: false });
    expect(vm.tileSource).toBe("local");
    expect(vm.fontSource).toBe("local");
    expect(vm.requiresNetwork).toBe(false);
  });

  it("Given an empty cache, When the map is built, Then the empty state is shown", () => {
    expect(buildMapViewModel({ parcels: [], online: false }).state).toBe("empty");
  });
});
