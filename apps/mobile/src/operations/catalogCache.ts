import type { ProductUse } from "@aylal/domain/phyto-controls";

export interface CatalogProduct {
  id: string;
  name: string;
  active_ingredients: { name: string; concentration?: string }[];
  uses: ProductUse[];
}
export interface Catalog {
  source_date: string;
  products: CatalogProduct[];
}

/** In-memory index of the downloaded phyto catalogue (offline, no wildcard: the query is matched literally). */
export function createCatalogCache(catalog: Catalog) {
  const byId = new Map(catalog.products.map((p) => [p.id, p]));
  return {
    sourceDate: () => catalog.source_date,
    get: (id: string): CatalogProduct | undefined => byId.get(id),
    search(query: string, limit = 20): CatalogProduct[] {
      const needle = query.trim().toLowerCase().slice(0, 80);
      return catalog.products
        .filter((p) => p.name.toLowerCase().includes(needle) || p.active_ingredients.some((a) => a.name.toLowerCase().includes(needle)))
        .slice(0, limit);
    },
  };
}
export type CatalogCache = ReturnType<typeof createCatalogCache>;
