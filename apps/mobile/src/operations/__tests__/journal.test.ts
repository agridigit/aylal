import { createJournal } from "../viewModels/journal";

const row = (id: string, performed_on: string, over = {}) => ({ id, farm_id: "f1", type: "irrigation", performed_on, status: "validated", parcel_ids: ["p1"], ...over });

describe("journal view model (R1-A2, R1-A5)", () => {
  it("given local operations when loading then they come in chronological order, newest first, with type, parcel and date", async () => {
    const j = createJournal({ list: async () => [row("a", "2026-11-01"), row("b", "2026-11-05"), row("c", "2026-11-03")], pendingIds: async () => new Set<string>() });
    const items = await j.load("f1");
    expect(items.map((i) => i.id)).toEqual(["b", "c", "a"]);
    expect(items[0]).toMatchObject({ type: "irrigation", performed_on: "2026-11-05", parcel_ids: ["p1"] });
  });

  it("given operations not yet uploaded when loading then they carry the to-send indicator", async () => {
    const j = createJournal({ list: async () => [row("a", "2026-11-01"), row("b", "2026-11-02")], pendingIds: async () => new Set(["b"]) });
    expect((await j.load("f1")).map((i) => [i.id, i.pending])).toEqual([["b", true], ["a", false]]);
  });

  it("given rows of several farms when loading then only the active farm is shown, offline included", async () => {
    const j = createJournal({ list: async () => [row("a", "2026-11-01"), row("x", "2026-11-02", { farm_id: "f2" })], pendingIds: async () => new Set<string>() });
    expect((await j.load("f1")).map((i) => i.id)).toEqual(["a"]);
    expect(await j.load(null)).toEqual([]);
  });

  it("given overdue planned operations when loading then they are flagged overdue and stay visible", async () => {
    const j = createJournal({ list: async () => [row("a", "2026-11-01", { status: "planned" }), row("b", "2026-11-20", { status: "planned" })], pendingIds: async () => new Set<string>() }, () => "2026-11-07");
    const items = await j.load("f1");
    expect(items.find((i) => i.id === "a")?.overdue).toBe(true);
    expect(items.find((i) => i.id === "b")?.overdue).toBe(false);
  });

  it("given an empty store when loading then the list is empty so the screen can show its empty state", async () => {
    const j = createJournal({ list: async () => [], pendingIds: async () => new Set<string>() });
    expect(await j.load("f1")).toEqual([]);
  });

  it("given a failing store when loading then the error is surfaced for the error state", async () => {
    const j = createJournal({ list: async () => { throw new Error("db"); }, pendingIds: async () => new Set<string>() });
    await expect(j.load("f1")).rejects.toThrow("db");
  });
});
