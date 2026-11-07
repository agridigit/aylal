/**
 * Split `total` across parcels in proportion to their areas, in 0.001 steps (largest remainder,
 * ties to the first parcel) so the shares always add up to the total. Vectors: f6_allocation.json.
 */
export function allocate(total: number, areas: readonly number[]): number[] {
  const sum = areas.reduce((a, b) => a + b, 0);
  if (areas.length === 0 || !(sum > 0)) throw new Error("allocation needs at least one parcel with an area");
  const units = Math.round(total * 1000);
  const exact = areas.map((a) => (units * a) / sum);
  const shares = exact.map((x) => Math.floor(x + 1e-9));
  let left = units - shares.reduce((a, b) => a + b, 0);
  const order = exact.map((x, i) => ({ i, r: x - shares[i]! })).sort((a, b) => b.r - a.r || a.i - b.i);
  for (const { i } of order) {
    if (left <= 0) break;
    shares[i]! += 1;
    left -= 1;
  }
  return shares.map((s) => s / 1000);
}
