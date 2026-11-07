export type SyncState = "pending" | "synced" | "conflict";
export type SyncEvent = "server_ack" | "conflict_detected" | "user_ack" | "local_edit";

export function deriveSyncState(i: {
  hasPendingOps: boolean;
  hasConflict: boolean;
  serverVersion: number | null;
}): SyncState {
  if (i.hasConflict) return "conflict";
  if (i.hasPendingOps || i.serverVersion === null) return "pending";
  return "synced";
}

const TRANSITIONS: Record<string, SyncState> = {
  "pending:server_ack": "synced",
  "pending:conflict_detected": "conflict",
  "conflict:user_ack": "synced",
  "synced:local_edit": "pending",
};

export function nextSyncState(state: SyncState, event: SyncEvent): SyncState {
  const next = TRANSITIONS[`${state}:${event}`];
  if (!next) throw new Error(`invalid sync transition: ${state} + ${event}`);
  return next;
}

/** The "not sent" indicator stays visible until the server confirms and the user acknowledges. */
export const isUnsent = (state: SyncState): boolean => state !== "synced";
