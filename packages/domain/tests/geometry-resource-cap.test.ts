import { describe, expect, it } from "vitest";
import { MAX_VERTICES, importFeatures, validateRing } from "../src/geometry";
import { polygon } from "./_f2";
import type { Pt } from "./_f2";

const CYCLE: Pt[] = [[-7.6, 33.57], [-7.598, 33.57], [-7.598, 33.572], [-7.599, 33.573], [-7.6, 33.572]];
const feature = (ring: Pt[]) => ({ type: "Feature", geometry: { type: "Polygon", coordinates: [ring] }, properties: {} });

describe("geometry resource cap (DoS)", () => {
  it("given a huge ring of repeated points when validating then it is refused fast as too_many_vertices", () => {
    // 5 000 raw points: enough to prove the raw cap without hanging the runner while the cap is missing.
    const ring = Array.from({ length: 5000 }, (_, i) => CYCLE[i % 5] as Pt);
    const start = performance.now();
    const r: any = validateRing(ring);
    expect(r.code).toBe("too_many_vertices");
    expect(performance.now() - start).toBeLessThan(100);
  });

  it("given a raw ring of 502 points with few distinct when validating then it is refused as too_many_vertices", () => {
    const ring = Array.from({ length: MAX_VERTICES + 2 }, (_, i) => CYCLE[i % 5] as Pt);
    expect((validateRing(ring) as any).code).toBe("too_many_vertices");
  });

  it("given 500 distinct vertices plus the closing point when validating then it is still accepted", () => {
    const p = polygon(500);
    expect(validateRing([...p, p[0] as Pt]).ok).toBe(true);
  });

  it("given 41 features of 500 vertices when importing then the total cap of 20000 throws too_many_vertices_total", () => {
    const p = polygon(500);
    const ring = [...p, p[0] as Pt];
    expect(() => importFeatures({ features: Array.from({ length: 41 }, () => feature(ring)) })).toThrow("too_many_vertices_total");
  });

  it("given 200 features of 500 vertices when importing then the total cap throws too_many_vertices_total", () => {
    const p = polygon(500);
    const ring = [...p, p[0] as Pt];
    expect(() => importFeatures({ features: Array.from({ length: 200 }, () => feature(ring)) })).toThrow("too_many_vertices_total");
  });

  it("given 200 features of 100 vertices when importing then exactly 20000 vertices are accepted", () => {
    const p = polygon(100);
    const ring = [...p, p[0] as Pt];
    expect(importFeatures({ features: Array.from({ length: 200 }, () => feature(ring)) }).valid).toHaveLength(200);
  });
});
