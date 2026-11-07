import type { SecureStore } from "../auth/secureStore";

const KEY = "active_farm";

export type FarmRef = { id: string; role: string };

/** Active farm choice, persisted; always falls back to a farm the user is a member of. */
export function createActiveFarm(store: SecureStore) {
  return {
    set: (farmId: string) => store.set(KEY, farmId),
    async resolve<T extends FarmRef>(farms: readonly T[]): Promise<T | null> {
      const chosen = await store.get(KEY);
      return farms.find((f) => f.id === chosen) ?? farms[0] ?? null;
    },
  };
}

/** Local rows of the active farm only (no farm active -> nothing). */
export function filterByFarm<T extends { farm_id: string }>(rows: readonly T[], farmId: string | null): T[] {
  return farmId === null ? [] : rows.filter((r) => r.farm_id === farmId);
}
