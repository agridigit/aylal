import { LIMITS } from "@aylal/domain/monitoring-limits";
import { CLOUD_MIN_CLEAR_PCT } from "@aylal/domain/vigor";

export interface VigorPoint {
  acquired_on: string;
  vigor: number;
  plant_moisture: number;
  clear_pct: number;
}

export interface VigorRecord {
  points: VigorPoint[];
  reliability: string;
  last_valid_map: { map_id: string; acquired_on: string } | null;
  processing: boolean;
}

export function buildVigorChart(points: readonly VigorPoint[]) {
  const kept = points
    .filter((p) => p.clear_pct >= CLOUD_MIN_CLEAR_PCT)
    .sort((a, b) => (a.acquired_on < b.acquired_on ? -1 : a.acquired_on > b.acquired_on ? 1 : 0))
    .slice(-LIMITS.seriesPoints)
    .map((p) => ({ date: p.acquired_on, vigor: p.vigor, plantMoisture: p.plant_moisture }));
  return { points: kept, seriesKeys: ["monitoring.vigor", "monitoring.plant_moisture"] as const };
}

export interface VigorState {
  state: "ready" | "empty";
  chart: ReturnType<typeof buildVigorChart>;
  map: { mapId: string; acquiredOn: string } | null;
  lowReliability: boolean;
  emptyReasonKey?: string;
}

export function createVigorViewModel(store: { read: (farmId: string, parcelId: string) => Promise<VigorRecord> }) {
  return {
    async load(farmId: string, parcelId: string): Promise<VigorState> {
      const rec = await store.read(farmId, parcelId);
      const chart = buildVigorChart(rec.points);
      const map = rec.last_valid_map === null ? null : { mapId: rec.last_valid_map.map_id, acquiredOn: rec.last_valid_map.acquired_on };
      const lowReliability = rec.reliability === "low";
      if (chart.points.length === 0 && map === null) {
        const emptyReasonKey = rec.processing ? "monitoring.vigor.processing" : "monitoring.vigor.no_valid_image";
        return { state: "empty", chart, map, lowReliability, emptyReasonKey };
      }
      return { state: "ready", chart, map, lowReliability };
    },
  };
}
