import { describe, expect, it } from "vitest";
import { blockInsideField } from "../src/block";
import { square } from "./_f2";

const field = square(-7.6, 33.57, 0.001);

describe("blockInsideField (overflow tolerated up to 1 percent of the block area)", () => {
  it("given a block fully inside when checking then true", () => {
    expect(blockInsideField(square(-7.5995, 33.5705, 0.0003), field)).toBe(true);
  });
  it("given a block sticking out by 0.5 percent of its area then true", () => {
    expect(blockInsideField(square(-7.6, 33.57, 0.0005).map(([x, y]) => [x - 0.0000025, y]) as any, field)).toBe(true);
  });
  it("given a block half outside when checking then false", () => {
    expect(blockInsideField(square(-7.6005, 33.57, 0.001), field)).toBe(false);
  });
  it("given a block elsewhere then false", () => {
    expect(blockInsideField(square(-7.5, 33.57, 0.0003), field)).toBe(false);
  });
});
