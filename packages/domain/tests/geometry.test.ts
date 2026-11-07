import { describe, expect, it } from "vitest";
import { importFeatures, isInMorocco, simplifyTrack, validateRing } from "../src/geometry";
import { polygon, square, vectors } from "./_f2";

describe("validateRing shared vectors (F2 geometry rules)", () => {
  for (const v of vectors("f2_self_intersection.json")) {
    it(`given ${v.name} when validating the ring then the verdict matches the shared vector`, () => {
      const r: any = validateRing(v.ring);
      expect(r.ok).toBe(v.expected.ok);
      if (!v.expected.ok) {
        expect(r.code).toBe(v.expected.code);
        if (v.expected.crossings !== undefined) expect(r.crossings).toHaveLength(v.expected.crossings);
      }
    });
  }
  it("given exactly 500 distinct vertices when validating then it is accepted", () => {
    expect(validateRing(polygon(500)).ok).toBe(true);
  });
  it("given 501 vertices when validating then it is refused as too_many_vertices", () => {
    const r: any = validateRing(polygon(501));
    expect(r.ok).toBe(false);
    expect(r.code).toBe("too_many_vertices");
  });
  it("given a non finite coordinate when validating then it is invalid_coordinates", () => {
    const r: any = validateRing([[Number.NaN, 33.5], [-7.5, 33.5], [-7.5, 33.6]]);
    expect(r.code).toBe("invalid_coordinates");
  });
});

describe("isInMorocco", () => {
  it("given Casablanca and Dakhla when checking then both are inside the national extent", () => {
    expect(isInMorocco([-7.6, 33.57])).toBe(true);
    expect(isInMorocco([-15.95, 23.7])).toBe(true);
  });
  it("given Paris, Madrid and Algiers when checking then they are outside", () => {
    expect(isInMorocco([2.35, 48.85])).toBe(false);
    expect(isInMorocco([-3.7, 40.4])).toBe(false);
    expect(isInMorocco([3.06, 36.75])).toBe(false);
  });
});

describe("simplifyTrack (Douglas-Peucker, 1.5 m)", () => {
  it("given collinear GPS points when simplifying then only the ends remain", () => {
    const pts: [number, number][] = Array.from({ length: 50 }, (_, i) => [-7.6 + i * 0.00001, 33.57]);
    expect(simplifyTrack(pts)).toEqual([pts[0], pts[49]]);
  });
  it("given a corner when simplifying then the corner is kept", () => {
    const pts: [number, number][] = [[-7.6, 33.57], [-7.599, 33.57], [-7.598, 33.57], [-7.598, 33.571], [-7.598, 33.572]];
    expect(simplifyTrack(pts)).toEqual([pts[0], pts[2], pts[4]]);
  });
  it("given a noisy track of 2000 points when simplifying then at most 500 vertices remain", () => {
    expect(simplifyTrack(polygon(2000, -7.6, 33.57, 0.01)).length).toBeLessThanOrEqual(500);
  });
});

describe("importFeatures", () => {
  const poly = (ring: [number, number][]) => ({ type: "Feature", properties: {}, geometry: { type: "Polygon", coordinates: [ring] } });
  it("given a valid polygon when importing then it is valid", () => {
    const r = importFeatures({ type: "FeatureCollection", features: [poly(square(-7.6, 33.57, 0.001))] });
    expect(r.valid).toHaveLength(1);
    expect(r.rejected).toHaveLength(0);
  });
  it("given a MultiPolygon when importing then it is split into one entity per polygon", () => {
    const multi = { type: "Feature", properties: {}, geometry: { type: "MultiPolygon", coordinates: [[square(-7.6, 33.57, 0.001)], [square(-7.5, 33.57, 0.001)]] } };
    expect(importFeatures({ type: "FeatureCollection", features: [multi] }).valid).toHaveLength(2);
  });
  it("given points, lines and bow ties when importing then each is rejected with a reason", () => {
    const point = { type: "Feature", properties: {}, geometry: { type: "Point", coordinates: [-7.6, 33.57] } };
    const line = { type: "Feature", properties: {}, geometry: { type: "LineString", coordinates: [[-7.6, 33.57], [-7.5, 33.57]] } };
    const bow = poly([[-7.6, 33.57], [-7.598, 33.572], [-7.598, 33.57], [-7.6, 33.572], [-7.6, 33.57]]);
    const r = importFeatures({ type: "FeatureCollection", features: [point, line, bow] });
    expect(r.valid).toHaveLength(0);
    expect(r.rejected.map((x: any) => x.reason)).toEqual(["not_a_polygon", "not_a_polygon", "self_intersection"]);
  });
  it("given more than 200 entities when importing then the file is refused", () => {
    const features = Array.from({ length: 201 }, () => poly(square(-7.6, 33.57, 0.001)));
    expect(() => importFeatures({ type: "FeatureCollection", features })).toThrow(/too_many_features/);
  });
});
