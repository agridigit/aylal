import { filterByFarm } from "../../farms/activeFarm";

export interface LocalOperation {
  id: string;
  farm_id: string;
  type: string;
  performed_on: string;
  status: string;
  parcel_ids: string[];
}
export interface JournalItem extends LocalOperation {
  pending: boolean;
  overdue: boolean;
}
export interface JournalStore {
  list(): Promise<LocalOperation[]>;
  pendingIds(): Promise<Set<string>>;
}

const isoToday = () => new Date().toISOString().slice(0, 10);

/** Local journal of the active farm: newest first, with the "to send" indicator and the derived overdue flag. */
export function createJournal(store: JournalStore, today: () => string = isoToday) {
  return {
    async load(farmId: string | null): Promise<JournalItem[]> {
      const [rows, pending] = await Promise.all([store.list(), store.pendingIds()]);
      const day = today();
      return filterByFarm(rows, farmId)
        .map((r) => ({ ...r, pending: pending.has(r.id), overdue: r.status === "planned" && r.performed_on < day }))
        .sort((a, b) => b.performed_on.localeCompare(a.performed_on) || b.id.localeCompare(a.id));
    },
  };
}
