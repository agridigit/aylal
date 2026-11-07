export const LOW_STORAGE_BYTES = 50 * 1024 * 1024;

export type StorageCheck =
  | { level: "ok" }
  | { level: "warning" | "blocking"; messageKey: string };

export function checkStorage(i: { freeBytes: number; requiredBytes: number }): StorageCheck {
  if (i.freeBytes < i.requiredBytes) return { level: "blocking", messageKey: "storage.full" };
  if (i.freeBytes < LOW_STORAGE_BYTES) return { level: "warning", messageKey: "storage.low" };
  return { level: "ok" };
}
