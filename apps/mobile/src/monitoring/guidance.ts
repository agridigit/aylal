import { guidance, type LatLon } from "@aylal/domain/guidance";

const ARRIVED_WITHIN_M = 15;

export interface ZoneTarget {
  id: string;
  centroid: { type: string; coordinates: number[] };
}

/** Flat on purpose: `arrived` and `guiding` carry the numbers; `position_unavailable` carries the fallback and the target. */
export interface GuidanceState {
  state: "arrived" | "guiding" | "position_unavailable";
  bearingDeg: number;
  distanceM: number;
  fallback?: "show_zone_on_map";
  target?: LatLon;
}

/** Heading and distance to a zone from the device position only; no network call. */
export function createGuidance(deps: { position: () => Promise<LatLon | null> }) {
  return {
    async toZone(zone: ZoneTarget): Promise<GuidanceState> {
      const target = { lat: zone.centroid.coordinates[1], lon: zone.centroid.coordinates[0] };
      let from: LatLon | null = null;
      try {
        from = await deps.position();
      } catch {
        from = null;
      }
      if (from === null) return { state: "position_unavailable", fallback: "show_zone_on_map", target } as GuidanceState;
      const g = guidance(from, target);
      if (g.distanceM <= ARRIVED_WITHIN_M) return { state: "arrived", bearingDeg: g.bearingDeg, distanceM: g.distanceM };
      return { state: "guiding", bearingDeg: g.bearingDeg, distanceM: g.distanceM };
    },
  };
}
