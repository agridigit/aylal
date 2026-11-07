import { areaM2 } from "./area";
import { intersectionAreaM2 } from "./overlap";
import type { Pt } from "./area";

export const BLOCK_OVERFLOW_RATIO = 0.01;

/** A block must lie inside its field; overflow up to 1 percent of the block area is tolerated. */
export function blockInsideField(block: readonly Pt[], field: readonly Pt[]): boolean {
  const total = areaM2(block);
  if (total <= 0) return false;
  return (total - intersectionAreaM2(block, field)) / total <= BLOCK_OVERFLOW_RATIO;
}
