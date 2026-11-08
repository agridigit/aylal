import { describeFreshness, type Freshness } from "../staleness";

const KNOWN_SOURCES = ["weather_alert", "irrigation_need", "health_risk", "vigor_anomaly", "overdue_operations"];

export interface StatusDetailInput {
  parcel_id: string;
  color: string;
  reason_key: string;
  computed_at: string;
  data_age_at?: string | null;
  imagery_reliability: string;
  items: readonly unknown[];
}

interface StatusItemInput {
  source: string;
  severity: string;
  reason_key: string;
  observed_at: string;
}

export interface StatusDetail {
  color: string;
  reasonKey: string;
  contributors: { source: string; sourceLabelKey: string; reasonKey: string; severity: string; observedAt: string }[];
  unavailableSources: string[];
  imageryLow: boolean;
  freshness: Freshness;
}

/** Contributors of a status; a source absent from the payload is simply not shown (no error). */
export function buildStatusDetail(status: StatusDetailInput, now: string): StatusDetail {
  return {
    color: status.color,
    reasonKey: status.reason_key,
    contributors: (status.items as readonly StatusItemInput[]).map((i) => ({
      source: i.source,
      sourceLabelKey: KNOWN_SOURCES.includes(i.source) ? `monitoring.source.${i.source}` : "monitoring.source.other",
      reasonKey: i.reason_key,
      severity: i.severity,
      observedAt: i.observed_at,
    })),
    unavailableSources: [],
    imageryLow: status.imagery_reliability === "low",
    freshness: describeFreshness(status.data_age_at ?? status.computed_at, now),
  };
}
