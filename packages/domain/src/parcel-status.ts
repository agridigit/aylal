export type Severity = "ok" | "watch" | "act";
export type Color = "green" | "orange" | "red";

export interface StatusSignal {
  source: string;
  severity: Severity | string;
  reason_key: string;
  observed_at: string;
  ttl_s: number;
  params?: Record<string, unknown>;
}

export interface StatusItem {
  source: string;
  severity: "watch" | "act";
  reasonKey: string;
  observedAt: string;
}

/** Priority of the sources when explaining a status (lower comes first). */
const PRIORITY = ["weather_alert", "irrigation_need", "health_risk", "vigor_anomaly", "overdue_operations"];
const RANK: Record<string, number> = { ok: 0, watch: 1, act: 2 };
const DOUBT_REASONS: Record<string, string> = {
  unknown_threshold: "status.threshold_unvalidated",
  stale_source: "status.stale_data",
  imagery_unreliable: "status.imagery_unreliable",
};
const NOTHING_TO_DO = "status.nothing_to_do";

const priorityOf = (source: string): number => {
  const i = PRIORITY.indexOf(source);
  return i === -1 ? PRIORITY.length : i;
};

/**
 * Colour of a parcel from live signals (expired ones ignored). The worst severity wins; the reason is the
 * highest-priority signal of that severity. Doubt alone is orange, never a falsely reassuring green.
 */
export function parcelStatus(
  signals: readonly StatusSignal[],
  now: string | Date,
  doubts: readonly string[] = [],
): { color: Color; reasonKey: string; items: StatusItem[] } {
  const at = new Date(now).getTime();
  const live = signals
    .filter((s) => (RANK[s.severity] ?? 0) > 0 && Date.parse(s.observed_at) + s.ttl_s * 1000 >= at)
    .sort((a, b) => (RANK[b.severity] ?? 0) - (RANK[a.severity] ?? 0) || priorityOf(a.source) - priorityOf(b.source));
  const items: StatusItem[] = live.map((s) => ({
    source: s.source, severity: s.severity as "watch" | "act", reasonKey: s.reason_key, observedAt: s.observed_at,
  }));
  const top = live[0];
  if (top !== undefined) return { color: top.severity === "act" ? "red" : "orange", reasonKey: top.reason_key, items };
  const doubt = doubts[0];
  if (doubt !== undefined) return { color: "orange", reasonKey: DOUBT_REASONS[doubt] ?? "status.doubt", items };
  return { color: "green", reasonKey: NOTHING_TO_DO, items };
}

export interface SortableParcel {
  id: string;
  color: string;
  contributors: number;
  name: string;
}

const COLOR_ORDER: Record<string, number> = { red: 0, orange: 1, green: 2 };

/** Red, orange, green; ties by contributors (more first) then name. */
export function sortParcels<T extends SortableParcel>(parcels: readonly T[]): T[] {
  return [...parcels].sort(
    (a, b) =>
      (COLOR_ORDER[a.color] ?? 3) - (COLOR_ORDER[b.color] ?? 3) ||
      b.contributors - a.contributors ||
      (a.name < b.name ? -1 : a.name > b.name ? 1 : 0),
  );
}
