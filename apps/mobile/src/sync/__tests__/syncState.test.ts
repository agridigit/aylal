import { deriveSyncState, nextSyncState, isUnsent } from "../syncState";

describe("sync state machine", () => {
  it("given a queued op when derived then pending", () => {
    expect(deriveSyncState({ hasPendingOps: true, hasConflict: false, serverVersion: null })).toBe("pending");
  });
  it("given no queued op and a known server version then synced", () => {
    expect(deriveSyncState({ hasPendingOps: false, hasConflict: false, serverVersion: 3 })).toBe("synced");
  });
  it("given has_conflict then conflict, even with nothing queued", () => {
    expect(deriveSyncState({ hasPendingOps: false, hasConflict: true, serverVersion: 3 })).toBe("conflict");
  });
  it("given pending when the server acknowledges then synced", () => {
    expect(nextSyncState("pending", "server_ack")).toBe("synced");
  });
  it("given pending when a concurrent field change is detected then conflict", () => {
    expect(nextSyncState("pending", "conflict_detected")).toBe("conflict");
  });
  it("given conflict when the user acknowledges then synced", () => {
    expect(nextSyncState("conflict", "user_ack")).toBe("synced");
  });
  it("given synced when the user edits locally then pending", () => {
    expect(nextSyncState("synced", "local_edit")).toBe("pending");
  });
  it("given an impossible transition then it throws", () => {
    expect(() => nextSyncState("synced", "user_ack")).toThrow();
  });
  it("given pending or conflict then the not-sent indicator stays visible until acknowledged", () => {
    expect(isUnsent("pending")).toBe(true);
    expect(isUnsent("conflict")).toBe(true);
    expect(isUnsent("synced")).toBe(false);
  });
  it("given a new phone with queued ops lost then a record with no server version is not shown as synced", () => {
    expect(deriveSyncState({ hasPendingOps: false, hasConflict: false, serverVersion: null })).toBe("pending");
  });
});
