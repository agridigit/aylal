import { planAlertNotifications } from "../alertNotifications";

const NOW = "2026-12-04T10:00:00Z";
const alert = (id: string, over: Record<string, unknown> = {}) => ({
  id, parcel_id: "p1", type: "frost", severity: "critical", status: "active", forecast_day: "2026-12-05",
  notify_at: "2026-12-04T16:00:00Z", revision: 1, advice_key: null, reason_key: "alert.frost", ...over,
});

describe("local alert notifications scheduled from synced alerts, offline (R2-A1, SC-003)", () => {
  it("given a frost alert due this evening then a local notification is planned at notify_at, before 18:00 Morocco time", () => {
    const plan = planAlertNotifications([alert("a1")], [], NOW);
    expect(plan.schedule).toEqual([expect.objectContaining({ alertId: "a1", at: "2026-12-04T16:00:00Z", revision: 1 })]);
    expect(plan.cancel).toEqual([]);
  });

  it("given an alert already planned with the same revision then nothing is planned twice", () => {
    const plan = planAlertNotifications([alert("a1")], [{ alertId: "a1", revision: 1, at: "2026-12-04T16:00:00Z" }], NOW);
    expect(plan).toEqual({ schedule: [], cancel: [] });
  });

  it("given the forecast changed (new revision) then the old notification is replaced, not duplicated", () => {
    const plan = planAlertNotifications([alert("a1", { revision: 2, notify_at: "2026-12-04T15:00:00Z" })], [{ alertId: "a1", revision: 1, at: "2026-12-04T16:00:00Z" }], NOW);
    expect(plan.cancel).toEqual(["a1"]);
    expect(plan.schedule).toEqual([expect.objectContaining({ alertId: "a1", at: "2026-12-04T15:00:00Z", revision: 2 })]);
  });

  it("given an alert resolved, dismissed or expired then its pending notification is cancelled and nothing is planned", () => {
    for (const status of ["resolved", "dismissed", "expired"]) {
      const plan = planAlertNotifications([alert("a1", { status })], [{ alertId: "a1", revision: 1, at: "2026-12-04T16:00:00Z" }], NOW);
      expect(plan).toEqual({ schedule: [], cancel: ["a1"] });
    }
  });

  it("given a notify_at already passed and not yet notified then it fires now (late data), not in the past", () => {
    const plan = planAlertNotifications([alert("a1", { notify_at: "2026-12-04T08:00:00Z" })], [], NOW);
    expect(plan.schedule[0].at).toBe(NOW);
  });

  it("given an alert without notify_at (not a frost) then no local notification is planned", () => {
    expect(planAlertNotifications([alert("a2", { type: "heavy_rain", notify_at: null })], [], NOW).schedule).toEqual([]);
  });

  it("given a strong wind alert with advice then the content carries the do-not-spray advice key", () => {
    const plan = planAlertNotifications([alert("a3", { type: "strong_wind", severity: "warning", advice_key: "do_not_spray", notify_at: "2026-12-04T16:00:00Z" })], [], NOW);
    expect(plan.schedule[0]).toMatchObject({ adviceKey: "do_not_spray", titleKey: expect.stringContaining("strong_wind") });
  });

  it("given alerts only the notification content uses i18n keys and no hard-coded text", () => {
    const n = planAlertNotifications([alert("a1")], [], NOW).schedule[0];
    expect(n.titleKey).toMatch(/^[a-z_.]+$/);
    expect(n.bodyKey).toMatch(/^[a-z_.]+$/);
  });
});
