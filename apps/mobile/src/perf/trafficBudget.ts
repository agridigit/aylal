export const TRAFFIC_BUDGET_BYTES = 5 * 1024 * 1024;

export interface TrafficRequest {
  kind: string;
  bytesIn: number;
  bytesOut: number;
  wifi?: boolean;
  onDemand?: boolean;
}

export const sessionTraffic = (requests: TrafficRequest[]): number =>
  requests.reduce((sum, r) => sum + r.bytesIn + r.bytesOut, 0);

// Satellite imagery is never fetched automatically on mobile data.
const isForbidden = (r: TrafficRequest) => r.kind === "satellite" && r.wifi !== true && r.onDemand !== true;

export const withinTrafficBudget = (requests: TrafficRequest[]): boolean =>
  !requests.some(isForbidden) && sessionTraffic(requests) < TRAFFIC_BUDGET_BYTES;
