import { describe, expect, it } from "vitest";
import * as mod from "../src/water-balance";
import { runVectors } from "./_f4";

describe("F4 water balance (shared vectors f4_water_balance.json)", () => {
  runVectors(mod as Record<string, unknown>, "f4_water_balance.json");
  it("given a 400-day window when replaying then it takes under 50 ms (injected data, no clock)", () => {
    const days = Array.from({ length: 400 }, (_, i) => ({
      day: new Date(Date.UTC(2026, 0, 1) + i * 86400000).toISOString().slice(0, 10),
      et0_mm: 5, kc: 0.8, rain_eff_mm: i % 7 === 0 ? 6 : 0, irrigation_net_mm: i % 5 === 0 ? 8 : 0,
    }));
    const t0 = performance.now();
    const out = (mod as any).replayBalance({ taw_mm: 80, initial_depletion_mm: 0, days });
    expect(performance.now() - t0).toBeLessThan(50);
    expect(out.days).toHaveLength(400);
  });
  it("given the same inputs when replayed twice then the result is identical (replayable journal)", () => {
    const days = [{ day: "2026-06-01", et0_mm: 5, kc: 1, rain_eff_mm: 0, irrigation_net_mm: 0 }];
    const a = (mod as any).replayBalance({ taw_mm: 60, initial_depletion_mm: 0, days });
    expect((mod as any).replayBalance({ taw_mm: 60, initial_depletion_mm: 0, days })).toEqual(a);
  });
});
