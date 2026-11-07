export interface RegistryEntry {
  id: string;
  entry_kind: string;
  supersedes_id: string | null;
  performed_on: string;
  dar_days: number | null;
  product_name: string | null;
}

export interface EarliestHarvest {
  date: string | null;
  harvestable_now: boolean;
  unknown_dar: boolean;
  limiting_product: string | null;
}

function addDays(date: string, days: number): string {
  const [y = 0, m = 1, d = 1] = date.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d + days)).toISOString().slice(0, 10);
}

/** Earliest harvest date: the longest pre-harvest interval among live applications. Mirror: harvest_date.py. */
export function earliestHarvest(entries: readonly RegistryEntry[], today: string): EarliestHarvest {
  const reversed = new Set(entries.filter((e) => e.entry_kind === "reversal" && e.supersedes_id).map((e) => e.supersedes_id));
  let date: string | null = null;
  let limiting: string | null = null;
  let unknown = false;
  for (const e of entries) {
    if (e.entry_kind !== "application" || reversed.has(e.id)) continue;
    if (e.dar_days == null) {
      unknown = true;
      continue;
    }
    const end = addDays(e.performed_on, e.dar_days);
    if (date === null || end > date) {
      date = end;
      limiting = e.product_name;
    }
  }
  return { date, harvestable_now: date === null || date <= today, unknown_dar: unknown, limiting_product: limiting };
}
