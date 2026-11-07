import { describe, expect, it } from "vitest";
import { MOTION, transitionDuration } from "../src/motion";

describe("motion", () => {
  it("Given standard motion, When reading durations, Then all are between 200 and 300 ms", () => {
    const values = Object.values(MOTION.durations) as number[];
    expect(values.length).toBeGreaterThan(0);
    for (const d of values) {
      expect(d).toBeGreaterThanOrEqual(200);
      expect(d).toBeLessThanOrEqual(300);
    }
  });

  it("Given reduce animations is off, When resolving a transition, Then it lasts 200 to 300 ms", () => {
    const d = transitionDuration({ reduceMotion: false });
    expect(d).toBeGreaterThanOrEqual(200);
    expect(d).toBeLessThanOrEqual(300);
  });

  it("Given reduce animations is on, When resolving a transition, Then it is removed or reduced", () => {
    expect(transitionDuration({ reduceMotion: true })).toBeLessThan(200);
  });
});
