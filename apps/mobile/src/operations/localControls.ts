import { phytoWarnings, type WarningCode } from "@aylal/domain/phyto-controls";
import type { CatalogCache } from "./catalogCache";

export interface LocalCheckInput {
  product_id?: string | null;
  free_product_name?: string | null;
  crop_slug: string | null;
  dose?: number | null;
  dose_unit?: string | null;
  applications_so_far: number;
}

/** Offline phyto controls against the cached catalogue; the server recomputes them on upload. */
export function createLocalControls(cache: CatalogCache) {
  return {
    check(input: LocalCheckInput): WarningCode[] {
      const product = input.product_id ? cache.get(input.product_id) : undefined;
      if (input.product_id && !product) return ["free_product_unchecked"];
      return phytoWarnings({ ...input, uses: product?.uses ?? [] });
    },
  };
}
