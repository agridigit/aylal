import { createMetric, type Measure, type MetricName } from "./metrics";

export const EXPORT_LOG_TAG = "AYLAL_MEASURES";

type Deps = { device: string; build: string; today?: () => string };

/** Frames per second over a window of requestAnimationFrame timestamps (ms); null if not measurable. */
export function fpsFromFrames(timestamps: number[]): number | null {
  if (timestamps.length < 2) return null;
  const span = timestamps[timestamps.length - 1]! - timestamps[0]!;
  return span > 0 ? ((timestamps.length - 1) * 1000) / span : null;
}

/** Collects real readings only; a metric never read is never exported. */
export function createMeasureSession({ device, build, today = () => new Date().toISOString().slice(0, 10) }: Deps) {
  const readings = new Map<MetricName, { value: number; unit: string }>();
  const set = (metric: MetricName, value: number, unit: string) => {
    if (!readings.has(metric)) readings.set(metric, { value, unit });
  };
  const exportAll = (): Measure[] =>
    [...readings].map(([metric, r]) => createMetric({ metric, value: r.value, unit: r.unit, device, date: today(), build }));
  return {
    markStartup: (ms: number) => set("startup_ms", ms, "ms"),
    markMapOpened: (ms: number) => set("map_open_ms", ms, "ms"),
    recordFps: (fps: number) => {
      readings.set("fps", { value: Math.round(fps * 10) / 10, unit: "fps" });
    },
    export: exportAll,
    exportLine: () => `${EXPORT_LOG_TAG} ${JSON.stringify(exportAll())}`,
  };
}

/** Provisional: values come from the emulator build, not from the reference 2 GB phone. */
export const measureSession = createMeasureSession({ device: "emulator aylal-2go (provisoire)", build: "e2e" });

let mapRequestedAt: number | null = null;
/** Tap on "open map" -> first commit of the map screen. */
export const mapOpenTimer = {
  start: () => {
    mapRequestedAt = Date.now();
  },
  stop: () => {
    if (mapRequestedAt !== null) measureSession.markMapOpened(Date.now() - mapRequestedAt);
    mapRequestedAt = null;
  },
};
