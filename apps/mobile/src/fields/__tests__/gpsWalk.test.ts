import { createGpsWalk } from "../gpsWalk";

// Contract (GREEN): createGpsWalk({ maxAccuracyM = 20 }) -> { push(sample), pause, resume, undoLast, status, finish }.
// sample = { lon, lat, accuracyM }. Samples come from an injected source (expo-location lives in the screen layer).
const walkSquare = (accuracyM: number) => {
  const w = createGpsWalk({ maxAccuracyM: 20 });
  const pts: [number, number][] = [[-7.6, 33.57], [-7.599, 33.57], [-7.599, 33.571], [-7.6, 33.571]];
  for (const [lon, lat] of pts) w.push({ lon, lat, accuracyM });
  return w;
};

describe("GPS walk around the field (R1-A1, R1-A4)", () => {
  it("given good fixes when finishing the walk then a closed ring with an area and the worst accuracy are returned", () => {
    const r = walkSquare(5).finish();
    expect(r.ok).toBe(true);
    if (r.ok) {
      expect(r.ring[0]).toEqual(r.ring[r.ring.length - 1]);
      expect(r.areaHa).toBeGreaterThan(0);
      expect(r.gpsAccuracyM).toBe(5);
    }
  });
  it("given a fix less precise than the threshold when pushing then it is ignored and the status is weak", () => {
    const w = createGpsWalk({ maxAccuracyM: 20 });
    w.push({ lon: -7.6, lat: 33.57, accuracyM: 80 });
    expect(w.status()).toEqual({ signal: "weak", points: 0, accuracyM: 80 });
  });
  it("given a good fix when pushing then the status is good with the point count", () => {
    const w = createGpsWalk({ maxAccuracyM: 20 });
    w.push({ lon: -7.6, lat: 33.57, accuracyM: 4 });
    expect(w.status()).toEqual({ signal: "good", points: 1, accuracyM: 4 });
  });
  it("given the farmer pauses when fixes arrive then they are not recorded until he resumes", () => {
    const w = createGpsWalk({ maxAccuracyM: 20 });
    w.pause();
    w.push({ lon: -7.6, lat: 33.57, accuracyM: 4 });
    expect(w.status().points).toBe(0);
    w.resume();
    w.push({ lon: -7.6, lat: 33.57, accuracyM: 4 });
    expect(w.status().points).toBe(1);
  });
  it("given a wrong stretch when undoing the last point then the walk continues from the previous one", () => {
    const w = walkSquare(5);
    w.undoLast();
    expect(w.status().points).toBe(3);
  });
  it("given a very dense walk of 3000 fixes when finishing then at most 500 vertices remain", () => {
    const w = createGpsWalk({ maxAccuracyM: 20 });
    for (let i = 0; i < 3000; i++) {
      const t = (2 * Math.PI * i) / 3000;
      w.push({ lon: -7.6 + 0.01 * Math.cos(t), lat: 33.57 + 0.01 * Math.sin(t), accuracyM: 3 });
    }
    const r = w.finish();
    expect(r.ok).toBe(true);
    if (r.ok) expect(r.ring.length - 1).toBeLessThanOrEqual(500);
  });
  it("given only weak fixes when finishing then it is refused as too_few_points", () => {
    const r = walkSquare(90).finish();
    expect(r).toMatchObject({ ok: false, code: "too_few_points" });
  });
  it("given a walk that crosses itself when finishing then it is refused with the crossings", () => {
    const w = createGpsWalk({ maxAccuracyM: 20 });
    for (const [lon, lat] of [[-7.6, 33.57], [-7.599, 33.571], [-7.599, 33.57], [-7.6, 33.571]]) w.push({ lon, lat, accuracyM: 3 });
    expect(w.finish()).toMatchObject({ ok: false, code: "self_intersection" });
  });
});
