import { createDrawSession } from "../drawSession";

// Contract (GREEN): createDrawSession({ mode }) -> { addPoint, undo, movePoint, points, validate, reset }
// validate() uses @aylal/domain (validateRing/areaHa/isInMorocco); no network, no expo module.
const A: [number, number] = [-7.6, 33.57];
const B: [number, number] = [-7.599, 33.57];
const C: [number, number] = [-7.599, 33.571];
const D: [number, number] = [-7.6, 33.571];

describe("draw by corner taps (R1-A4)", () => {
  it("given four corner taps when validating then the ring is closed with a computed area in hectares", () => {
    const s = createDrawSession({ mode: "taps" });
    [A, B, C, D].forEach((p) => s.addPoint(p));
    const r = s.validate();
    expect(r.ok).toBe(true);
    if (r.ok) {
      expect(r.ring[0]).toEqual(r.ring[r.ring.length - 1]);
      expect(r.areaHa).toBeGreaterThan(0);
      expect(r.areaHa).toBeCloseTo(Math.round(r.areaHa * 100) / 100, 1);
    }
  });
  it("given fewer than three taps when validating then it is refused as too_few_points", () => {
    const s = createDrawSession({ mode: "taps" });
    s.addPoint(A);
    s.addPoint(B);
    expect(s.validate()).toMatchObject({ ok: false, code: "too_few_points" });
  });
  it("given a wrong tap when undoing then the last point is removed and drawing can continue", () => {
    const s = createDrawSession({ mode: "taps" });
    [A, B, C].forEach((p) => s.addPoint(p));
    s.undo();
    expect(s.points()).toEqual([A, B]);
  });
  it("given a placed corner when moving it then the correction is kept and the area is recomputed", () => {
    const s = createDrawSession({ mode: "taps" });
    [A, B, C, D].forEach((p) => s.addPoint(p));
    const before = (s.validate() as { areaHa: number }).areaHa;
    s.movePoint(2, [-7.598, 33.572]);
    expect(s.points()[2]).toEqual([-7.598, 33.572]);
    expect((s.validate() as { areaHa: number }).areaHa).toBeGreaterThan(before);
  });
});

describe("self-crossing drawing (R1-A3)", () => {
  it("given a bow tie when validating then it reports the crossing points for the visual explanation", () => {
    const s = createDrawSession({ mode: "taps" });
    [A, C, B, D].forEach((p) => s.addPoint(p));
    const r = s.validate();
    expect(r).toMatchObject({ ok: false, code: "self_intersection" });
    expect((r as { crossings: unknown[] }).crossings.length).toBeGreaterThan(0);
  });
  it("given a refused drawing when resetting then the session starts over empty", () => {
    const s = createDrawSession({ mode: "taps" });
    [A, C, B, D].forEach((p) => s.addPoint(p));
    s.reset();
    expect(s.points()).toEqual([]);
  });
});

describe("limits (CL)", () => {
  it("given a zero-area drawing (three collinear taps) when validating then it is refused", () => {
    const s = createDrawSession({ mode: "taps" });
    [A, [-7.5995, 33.57], B].forEach((p) => s.addPoint(p as [number, number]));
    expect(s.validate().ok).toBe(false);
  });
  it("given a drawing outside Morocco when validating then it is refused as outside_morocco", () => {
    const s = createDrawSession({ mode: "taps" });
    [[2.35, 48.85], [2.351, 48.85], [2.351, 48.851]].forEach((p) => s.addPoint(p as [number, number]));
    expect(s.validate()).toMatchObject({ ok: false, code: "outside_morocco" });
  });
  it("given 501 distinct taps when adding the last one then it is refused (500 vertices maximum)", () => {
    const s = createDrawSession({ mode: "taps" });
    for (let i = 0; i < 500; i++) s.addPoint([-7.6 + 0.0001 * Math.cos(i), 33.57 + 0.0001 * Math.sin(i)]);
    expect(() => s.addPoint([-7.5, 33.5])).toThrow(/too_many_vertices/);
  });
});
