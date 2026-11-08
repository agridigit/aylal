/** A zone is anomalous when its vigor drop and size both reach the reference thresholds. */
export function isAnomalousZone(
  zone: { dropScore: number; pixels: number },
  params: { anomalyDrop: number; anomalyMinPixels: number },
): boolean {
  return zone.dropScore >= params.anomalyDrop && zone.pixels >= params.anomalyMinPixels;
}

/** Resolved when the two most recent valid scenes are above the threshold. */
export function isResolved(recentVigor: readonly number[], threshold: number): boolean {
  if (recentVigor.length < 2) return false;
  return recentVigor.slice(-2).every((v) => v > threshold);
}
