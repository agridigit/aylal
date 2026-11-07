import { describe, expect, it } from "vitest";
import { planSeasonStart } from "../src/season";
import { vectors } from "./_f2";

describe("planSeasonStart shared vectors (R6-A1 to R6-A3)", () => {
  for (const v of vectors("f2_season_rotation.json")) {
    it(`given ${v.name} when planning the start then the plan matches the shared vector`, () => {
      const r: any = planSeasonStart(v.active, v.cropId, v.closeIds);
      expect(r.ok).toBe(v.expected.ok);
      if (v.expected.ok) expect([...r.closeIds].sort()).toEqual(v.expected.closeIds);
      else expect(r.code).toBe(v.expected.code);
    });
  }
});
