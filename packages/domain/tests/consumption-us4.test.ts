/** T069 (US4) - water consumption totals: m3 and m3/ha per parcel and for the season, the empty state. The shared rule does not exist
 *  yet (imported inside each test). Python mirror: services/api/tests/unit/test_f4_consumption.py. */
import { describe, expect, it } from "vitest";

const load = async () => await import("../src/consumption");

describe("F4 US4 consumption summary", () => {
  it("given irrigations on a 2 ha parcel when summarising then the volume and the volume per hectare are given (R4-A1)", async () => {
    const { summariseConsumption } = await load();
    const out = summariseConsumption({ parcels: [{ parcel_id: "a", volume_m3: 120, area_ha: 2 }] });
    expect(out.parcels[0]).toMatchObject({ parcel_id: "a", volume_m3: 120, volume_m3_per_ha: 60 });
    expect(out.total_m3).toBe(120);
    expect(out.empty).toBe(false);
  });

  it("given two parcels of different areas when comparing then each ratio is its own volume over its own area (R4-A2)", async () => {
    const { summariseConsumption } = await load();
    const out = summariseConsumption({ parcels: [{ parcel_id: "a", volume_m3: 100, area_ha: 1 }, { parcel_id: "b", volume_m3: 150, area_ha: 5 }] });
    expect(out.parcels.map((p: { volume_m3_per_ha: number }) => p.volume_m3_per_ha)).toEqual([100, 30]);
    expect(out.total_m3).toBe(250);
  });

  it("given a season without any irrigation when summarising then the state is empty with zero totals (R4-A3)", async () => {
    const { summariseConsumption } = await load();
    const out = summariseConsumption({ parcels: [{ parcel_id: "a", volume_m3: 0, area_ha: 2 }, { parcel_id: "b", volume_m3: 0, area_ha: 1 }] });
    expect(out).toMatchObject({ empty: true, total_m3: 0 });
    expect(summariseConsumption({ parcels: [] })).toMatchObject({ empty: true, total_m3: 0 });
  });

  it.each([[null], [0]])("given a parcel area of %s when summarising then the ratio is null, never infinite nor invented", async (area) => {
    const { summariseConsumption } = await load();
    const p = summariseConsumption({ parcels: [{ parcel_id: "a", volume_m3: 50, area_ha: area }] }).parcels[0];
    expect(p.volume_m3_per_ha).toBeNull();
    expect(p.volume_m3).toBe(50);
  });

  it("given the summary when serialised then it carries no author and no note (aggregate only)", async () => {
    const { summariseConsumption } = await load();
    expect(JSON.stringify(summariseConsumption({ parcels: [{ parcel_id: "a", volume_m3: 1, area_ha: 1 }] }))).not.toMatch(/author|note/);
  });
});
