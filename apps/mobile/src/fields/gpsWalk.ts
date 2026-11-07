import { simplifyTrack } from "@aylal/domain/geometry";
import type { Pt } from "@aylal/domain/geometry";
import { validateDrawn } from "./drawSession";
import type { DrawResult } from "./drawSession";

export type GpsSample = { lon: number; lat: number; accuracyM: number };

/** Samples come from an injected source (expo-location lives in the screen layer). */
export function createGpsWalk(opts: { maxAccuracyM?: number } = {}) {
  const maxAccuracyM = opts.maxAccuracyM ?? 20;
  const kept: { pt: Pt; accuracyM: number }[] = [];
  let paused = false;
  let last: number | null = null;
  let weak = true;
  return {
    push(s: GpsSample) {
      if (paused) return;
      last = s.accuracyM;
      weak = !(s.accuracyM <= maxAccuracyM);
      if (!weak) kept.push({ pt: [s.lon, s.lat], accuracyM: s.accuracyM });
    },
    pause() {
      paused = true;
    },
    resume() {
      paused = false;
    },
    undoLast() {
      kept.pop();
    },
    status: () => ({ signal: weak ? ("weak" as const) : ("good" as const), points: kept.length, accuracyM: last }),
    finish(): DrawResult & { gpsAccuracyM?: number } {
      if (kept.length < 3) return { ok: false, code: "too_few_points" };
      const r = validateDrawn(simplifyTrack(kept.map((k) => k.pt)));
      return r.ok ? { ...r, gpsAccuracyM: Math.max(...kept.map((k) => k.accuracyM)) } : r;
    },
  };
}
