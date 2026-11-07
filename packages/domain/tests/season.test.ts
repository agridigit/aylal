import { describe, expect, it } from "vitest";
import { canStartSeason, seasonDate } from "../src/season";
import { vectors } from "./_f2";

describe("season rules shared vectors", () => {
  for (const v of vectors("f2_season_rules.json")) {
    it(`given ${v.name} when applying ${v.fn} then the verdict matches the shared vector`, () => {
      if (v.fn === "canStartSeason") {
        expect(canStartSeason(v.active, v.cropId)).toBe(v.expected);
      } else {
        const r: any = seasonDate({ cycle: v.cycle }, v.input, v.today);
        expect(r.ok).toBe(v.expected.ok);
        if (!v.expected.ok) expect(r.code).toBe(v.expected.code);
      }
    });
  }
});
