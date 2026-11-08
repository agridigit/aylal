/** A scene is published only when at least 80 % of the parcel is clear (FR-007); never more than 100 %. */
export const CLOUD_MIN_CLEAR_PCT = 80;

export function isScenePublishable(clearPct: number, minClearPct: number = CLOUD_MIN_CLEAR_PCT): boolean {
  return Number.isFinite(clearPct) && clearPct >= minClearPct && clearPct <= 100;
}
