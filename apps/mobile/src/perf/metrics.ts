export const THRESHOLDS = {
  startup_ms: 3000,
  map_open_ms: 2000,
  fps: 60,
  apk_size_mb: 40,
  daily_traffic_mb: 5,
} as const;

export type MetricName = keyof typeof THRESHOLDS;
export type Verdict = "met" | "not_met";

export interface Measure {
  metric: MetricName;
  value: number;
  unit: string;
  threshold: number;
  device: string;
  date: string;
  verdict: Verdict;
  build: string;
}

export interface MeasureInput {
  metric: MetricName;
  value: number;
  unit: string;
  device: string;
  date: string;
  build: string;
}

// fps is a minimum to reach; every other metric is a maximum not to exceed.
export function verdictFor(metric: MetricName, value: number): Verdict {
  const t = THRESHOLDS[metric];
  const ok = metric === "fps" ? value >= t : value <= t;
  return ok ? "met" : "not_met";
}

export function createMetric(i: MeasureInput): Measure {
  return {
    metric: i.metric,
    value: i.value,
    unit: i.unit,
    threshold: THRESHOLDS[i.metric],
    device: i.device,
    date: i.date,
    verdict: verdictFor(i.metric, i.value),
    build: i.build,
  };
}

const FIELDS = ["metric", "value", "unit", "threshold", "device", "date", "verdict", "build"] as const;

export function parseMeasure(json: string): Measure {
  const o = JSON.parse(json);
  for (const f of FIELDS) if (o?.[f] === undefined) throw new Error(`measure: missing field ${f}`);
  if (o.verdict !== "met" && o.verdict !== "not_met") throw new Error("measure: invalid verdict");
  return o as Measure;
}
