import { readFileSync } from "node:fs";
import { join } from "node:path";
import { createGuidance } from "../guidance";

const v = JSON.parse(readFileSync(join(__dirname, "../../../../../packages/domain/vectors/f3_guidance.json"), "utf-8"));
const zone = (lat: number, lon: number) => ({ id: "z1", centroid: { type: "Point", coordinates: [lon, lat] } });

describe("GPS guidance to a zone, heading and distance computed on the device (R4-A2)", () => {
  for (const c of v.cases) {
    it(`given the phone south-west of a target to the ${c.name} then heading and distance match the shared vectors`, async () => {
      const g = createGuidance({ position: async () => v.from });
      const s = await g.toZone(zone(c.to.lat, c.to.lon));
      if (c.distance_m === 0) { expect(s.state).toBe("arrived"); return; }
      expect(s.state).toBe("guiding");
      expect(Math.abs(((s.bearingDeg - c.bearing + 540) % 360) - 180)).toBeLessThanOrEqual(v.tolerance.bearing_deg);
      expect(Math.abs(s.distanceM - c.distance_m)).toBeLessThanOrEqual(Math.max(v.tolerance.distance_abs_m, c.distance_m * v.tolerance.distance_ratio));
    });
  }

  it("given the phone within 15 metres of the zone then the user is told they arrived", async () => {
    const g = createGuidance({ position: async () => ({ lat: 33.57, lon: -7.6 }) });
    expect((await g.toZone(zone(33.57005, -7.6))).state).toBe("arrived");
  });

  it("given no network then guidance still works from the device position alone, with no network call", async () => {
    const fetchSpy = jest.fn();
    (globalThis as any).fetch = fetchSpy;
    const g = createGuidance({ position: async () => v.from });
    await g.toZone(zone(33.571, -7.6));
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("given GPS unavailable then the fallback is to show the zone on the map, with the zone centroid", async () => {
    const g = createGuidance({ position: async () => null });
    expect(await g.toZone(zone(33.571, -7.6))).toEqual({ state: "position_unavailable", fallback: "show_zone_on_map", target: { lat: 33.571, lon: -7.6 } });
  });

  it("given the position read fails then it falls back instead of throwing", async () => {
    const g = createGuidance({ position: async () => { throw new Error("denied"); } });
    expect((await g.toZone(zone(33.571, -7.6))).state).toBe("position_unavailable");
  });
});
