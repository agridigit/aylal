/** T052 (US2) - R2-A6: the rule that picks the advice to serve (today's, else the last known one, dated, confidence lowered) is shared
 *  (FR-019). New vector file `f4_us2_last_known.json`; the module does not exist yet (imported inside the test). */
import { describe, expect, it } from "vitest";
import { matches, vectors } from "./_f4";

describe("F4 US2 served advice (shared vectors f4_us2_last_known.json)", () => {
  for (const v of vectors("f4_us2_last_known.json")) {
    it(`given ${v.name} then select_served_plan matches the shared vector`, async () => {
      const mod = (await import("../src/irrigation-last-known")) as Record<string, (i: unknown) => unknown>;
      expect(typeof mod.selectServedPlan).toBe("function");
      matches(mod.selectServedPlan!(structuredClone(v.input)), v.expected, v.tol ?? 0.01, v.exact ?? false);
    });
  }
});
