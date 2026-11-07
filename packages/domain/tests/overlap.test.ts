import { describe, expect, it } from "vitest";
import { overlapWarnings } from "../src/overlap";
import { vectors } from "./_f2";

describe("overlapWarnings shared vectors (> 1 percent of the smallest area, non blocking)", () => {
  for (const v of vectors("f2_overlap.json")) {
    it(`given ${v.name} when checking overlaps then the ids match the shared vector`, () => {
      expect([...overlapWarnings(v.ring, v.others)].sort()).toEqual(v.expected);
    });
  }
});
