import { describe, expect, it } from "vitest";
import { mergeFields } from "../src/merge";
import { vectors } from "./_f2";

describe("mergeFields shared vectors", () => {
  for (const v of vectors("f2_merge.json")) {
    it(`given ${v.name} when merging then the result matches the shared vector`, () => {
      const r: any = mergeFields(v.survivor, v.others, v.seasons);
      expect(r.ok).toBe(v.expected.ok);
      if (!v.expected.ok) return expect(r.code).toBe(v.expected.code);
      expect(Math.abs(r.areaHa - v.expected.areaHa) / v.expected.areaHa).toBeLessThan(0.005);
      expect([...r.keptSeasonIds].sort()).toEqual(v.expected.keptSeasonIds);
      expect([...r.droppedSeasonIds].sort()).toEqual(v.expected.droppedSeasonIds);
    });
  }
});
