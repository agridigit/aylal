import { earliestHarvest, type EarliestHarvest, type RegistryEntry } from "@aylal/domain/harvest-date";

/** Local earliest harvest date from the synced registry lines of a parcel (works offline). */
export function localHarvestDate(entries: readonly RegistryEntry[], today: string): EarliestHarvest {
  return earliestHarvest(entries, today);
}
