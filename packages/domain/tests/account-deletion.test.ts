import { describe, expect, it } from "vitest";
import { DELETION_GRACE_DAYS, deletionDeadline, deletionImpact } from "../src/account-deletion";

describe("account deletion rules (R8-A1, R8-A3)", () => {
  it("given the grace period then it is 30 days", () => {
    expect(DELETION_GRACE_DAYS).toBe(30);
  });
  it("given a confirmed request when computing the deadline then it is exactly 30 days later", () => {
    expect(deletionDeadline(new Date("2026-11-07T12:00:00Z")).toISOString()).toBe("2026-12-07T12:00:00.000Z");
  });
  it("given an owner of a farm with other members then the farm is listed in the impact", () => {
    expect(deletionImpact([{ farm_id: "f1", name: "Atlas", role: "owner", other_members: 2 }])).toEqual([
      { farm_id: "f1", name: "Atlas", other_members: 2 },
    ]);
  });
  it("given a sole owner, a manager or a worker then nothing is listed", () => {
    expect(
      deletionImpact([
        { farm_id: "a", name: "A", role: "owner", other_members: 0 },
        { farm_id: "b", name: "B", role: "manager", other_members: 3 },
        { farm_id: "c", name: "C", role: "worker", other_members: 3 },
      ]),
    ).toEqual([]);
  });
});
