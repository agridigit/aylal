/** T055 (US2) - R2-A6 offline, SC-005: the local balance equals the server's on the shared vectors; the worker never gets a local
 *  reserve (decisions point 19). Modules do not exist yet: imported inside each test. */
import { readFileSync } from "node:fs";

const load = async () => await import("../localBalance");
const vectorFile = JSON.parse(readFileSync(require.resolve("../../../../../packages/domain/vectors/f4_water_balance.json"), "utf-8"));
const VECTORS: any[] = Array.isArray(vectorFile) ? vectorFile : vectorFile.cases;
const close = (a: number, b: number) => Math.abs(a - b) <= 0.01;

describe("local water balance (staff)", () => {
  it.each(VECTORS.filter((v) => v.fn === "replay_balance").map((v) => [v.name, v]))(
    "given the shared vector '%s' when replaying locally then the result equals the server's (SC-005)",
    async (_name, v: any) => {
      const { createLocalBalance } = await load();
      const out = createLocalBalance({ role: "owner" }).replay(structuredClone(v.input));
      const want = v.expected;
      if (want.days) {
        expect(out.days).toHaveLength(want.days.length);
        want.days.forEach((d: any, i: number) => expect(close(out.days[i].depletion_mm, d.depletion_mm)).toBe(true));
      }
      if (want.unavailable_reason) expect(out.unavailable_reason).toBe(want.unavailable_reason);
    },
  );

  it("given 30 simulated offline days with an irrigation each third day when replaying then the local depletion equals the server's for the same inputs", async () => {
    const { createLocalBalance } = await load();
    const days = Array.from({ length: 30 }, (_, i) => ({
      day: `2026-06-${String(i + 1).padStart(2, "0")}`, et0_mm: 5, kc: 0.7, rain_eff_mm: i % 10 === 9 ? 4 : 0, irrigation_net_mm: i % 3 === 2 ? 12 : 0,
    }));
    const local = createLocalBalance({ role: "manager" }).replay({ taw_mm: 50, initial_depletion_mm: 0, days });
    const domain = (await import("@aylal/domain/water-balance")).replayBalance({ taw_mm: 50, initial_depletion_mm: 0, days } as never);
    expect(local.days.map((d: any) => d.depletion_mm)).toEqual(domain.days!.map((d: any) => d.depletion_mm));
  });

  it("given an irrigation recorded offline today when reading the local balance then it is counted immediately", async () => {
    const { createLocalBalance } = await load();
    const vm = createLocalBalance({ role: "owner" });
    const before = vm.replay({ taw_mm: 50, initial_depletion_mm: 30, days: [{ day: "2026-06-04", et0_mm: 5, kc: 0.7, rain_eff_mm: 0, irrigation_net_mm: 0 }] });
    const after = vm.replay({ taw_mm: 50, initial_depletion_mm: 30, days: [{ day: "2026-06-04", et0_mm: 5, kc: 0.7, rain_eff_mm: 0, irrigation_net_mm: 10.8 }] });
    expect(before.days[0].depletion_mm - after.days[0].depletion_mm).toBeCloseTo(10.8, 1);
  });

  it("given a last synced advice when offline then it is served dated with a lowered confidence", async () => {
    const { createLocalBalance } = await load();
    const advice = { parcel_id: "p1", for_date: "2026-06-03", kind: "irrigate", confidence: "high", total_minutes: 90, assumptions: [] };
    const out = createLocalBalance({ role: "owner" }).servedAdvice({ plans: [advice], today: "2026-06-04" });
    expect(out.served).toMatchObject({ for_date: "2026-06-03", kind: "irrigate" });
    expect(out.is_last_known).toBe(true);
    expect(out.confidence).toBe("low");
  });
});

describe("local water balance (worker, decisions point 19)", () => {
  it("given a worker when asking for a local reserve then none is computed and no soil data is exposed", async () => {
    const { createLocalBalance } = await load();
    const out = createLocalBalance({ role: "worker" }).replay({ taw_mm: 50, initial_depletion_mm: 30, days: [] });
    expect(out).toEqual({ unavailable_reason: "worker_view", days: [] });
  });

  it("given a worker when reading the advice offline then only the last synced worker view is used, without any soil, water or leaching key", async () => {
    const { createLocalBalance } = await load();
    const synced = {
      parcel_id: "p1", for_date: "2026-06-04", kind: "irrigate", confidence: "medium", total_minutes: 60,
      assumptions: [{ key: "et0", value: 5, source: "gateway" }, { key: "kc", value: 0.7, source: "referential" }],
    };
    const out = createLocalBalance({ role: "worker" }).servedAdvice({ plans: [synced], today: "2026-06-04" });
    expect(out.served).toMatchObject({ kind: "irrigate", total_minutes: 60 });
    expect(JSON.stringify(out)).not.toMatch(/taw|soil|ece|ecw|salin|leaching|water_source|analysis/);
  });

  it("given a worker view that carries a forbidden key when serving then the key is dropped, deny by default", async () => {
    const { createLocalBalance } = await load();
    const dirty = { parcel_id: "p1", for_date: "2026-06-04", kind: "irrigate", confidence: "medium", total_minutes: 60, leaching_fraction: 0.1,
      assumptions: [{ key: "et0", value: 5, source: "gateway" }, { key: "soil_texture", value: "clay", source: "referential" }, { key: "x_future", value: 1, source: "computed" }] };
    const out = createLocalBalance({ role: "worker" }).servedAdvice({ plans: [dirty], today: "2026-06-04" });
    expect(out.served.leaching_fraction).toBeUndefined();
    expect(out.served.assumptions.map((a: any) => a.key)).toEqual(["et0"]);
  });
});
