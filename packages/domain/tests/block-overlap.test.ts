import { describe, expect, it } from "vitest";
import { blocksOverlap } from "../src/block";
import { square } from "./_f2";

describe("blocksOverlap (tolerance 1 percent of the smaller block)", () => {
  it("given two disjoint blocks when comparing then no overlap", () => {
    expect(blocksOverlap(square(-7.6, 33.57, 0.0005), square(-7.599, 33.57, 0.0005))).toBe(false);
  });
  it("given two blocks sharing only an edge when comparing then no overlap", () => {
    expect(blocksOverlap(square(-7.6, 33.57, 0.0005), square(-7.5995, 33.57, 0.0005))).toBe(false);
  });
  it("given a block half covering another when comparing then overlap", () => {
    expect(blocksOverlap(square(-7.6, 33.57, 0.0005), square(-7.59975, 33.57, 0.0005))).toBe(true);
  });
  it("given a block nested in another when comparing then overlap", () => {
    expect(blocksOverlap(square(-7.6, 33.57, 0.001), square(-7.5997, 33.5703, 0.0002))).toBe(true);
  });
});
