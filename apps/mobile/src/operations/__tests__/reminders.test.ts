import { createReminders } from "../reminders";

type Scheduled = { id: string; at: Date; title: string; data: Record<string, string> };
function fakeScheduler() {
  const scheduled = new Map<string, Scheduled>();
  const network: string[] = [];
  return {
    scheduled,
    network,
    scheduleLocal: async (n: Scheduled) => void scheduled.set(n.id, n),
    cancel: async (id: string) => void scheduled.delete(id),
    getExpoPushTokenAsync: () => { network.push("push-token"); throw new Error("no push provider allowed"); },
    fetch: () => { network.push("fetch"); throw new Error("no network allowed"); },
  };
}
const planned = (id: string, performed_on: string, status = "planned") => ({ id, performed_on, status, type: "irrigation", parcel_name: "Haut" });
const NOW = new Date("2026-11-07T10:00:00");

describe("local reminders (R4-A1, R4-A2)", () => {
  it("given a planned operation when scheduling then a local notification is set for the morning of the day, offline", async () => {
    const s = fakeScheduler();
    await createReminders(s, () => NOW).schedule(planned("op1", "2026-11-08"));
    const n = s.scheduled.get("op1")!;
    expect(n.at.getFullYear()).toBe(2026);
    expect([n.at.getMonth(), n.at.getDate(), n.at.getHours()]).toEqual([10, 8, 8]);
    expect(n.data).toMatchObject({ operation_id: "op1" });
    expect(s.network).toEqual([]);
  });

  it("given the reminder module then no push token and no network call is ever used", async () => {
    const s = fakeScheduler();
    const r = createReminders(s, () => NOW);
    await r.schedule(planned("op1", "2026-11-08"));
    await r.reschedule(planned("op1", "2026-11-09"));
    await r.cancel("op1");
    await r.syncAll([planned("op2", "2026-11-10")]);
    expect(s.network).toEqual([]);
  });

  it("given a notification text when scheduling then it is an i18n key and not hard coded text", async () => {
    const s = fakeScheduler();
    await createReminders(s, () => NOW).schedule(planned("op1", "2026-11-08"));
    expect(s.scheduled.get("op1")!.title).toMatch(/^reminders\./);
  });

  it("given a done or cancelled operation when scheduling then nothing is scheduled", async () => {
    const s = fakeScheduler();
    const r = createReminders(s, () => NOW);
    await r.schedule(planned("a", "2026-11-08", "validated"));
    await r.schedule(planned("b", "2026-11-08", "cancelled"));
    expect(s.scheduled.size).toBe(0);
  });

  it("given an operation marked done or cancelled when cancelling then its reminder disappears", async () => {
    const s = fakeScheduler();
    const r = createReminders(s, () => NOW);
    await r.schedule(planned("op1", "2026-11-08"));
    await r.cancel("op1");
    expect(s.scheduled.has("op1")).toBe(false);
  });

  it("given a rescheduled operation when rescheduling then the previous reminder is replaced by one on the new day", async () => {
    const s = fakeScheduler();
    const r = createReminders(s, () => NOW);
    await r.schedule(planned("op1", "2026-11-08"));
    await r.reschedule(planned("op1", "2026-11-12"));
    expect(s.scheduled.size).toBe(1);
    expect(s.scheduled.get("op1")!.at.getDate()).toBe(12);
  });

  it("given a day already past when scheduling then no notification is set in the past (the operation shows as overdue instead)", async () => {
    const s = fakeScheduler();
    await createReminders(s, () => NOW).schedule(planned("old", "2026-11-01"));
    expect(s.scheduled.size).toBe(0);
  });

  it("given the synced list after a long offline period when rebuilding then exactly the future planned operations are scheduled", async () => {
    const s = fakeScheduler();
    const r = createReminders(s, () => NOW);
    await r.schedule(planned("gone", "2026-11-20"));
    await r.syncAll([planned("a", "2026-11-09"), planned("b", "2026-11-15", "validated"), planned("c", "2026-11-03"), planned("d", "2026-11-30")]);
    expect([...s.scheduled.keys()].sort()).toEqual(["a", "d"]);
  });

  it("given more than 500 planned operations when rebuilding then at most 500 are scheduled", async () => {
    const s = fakeScheduler();
    const many = Array.from({ length: 520 }, (_, i) => planned(`o${i}`, "2026-12-01"));
    await createReminders(s, () => NOW).syncAll(many);
    expect(s.scheduled.size).toBeLessThanOrEqual(500);
  });
});
