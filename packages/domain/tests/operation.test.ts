import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { initialStatus, isOverdue, nextStatus, reschedule } from "../src/operation";

const m = JSON.parse(readFileSync(new URL("../vectors/f6_status_machine.json", import.meta.url), "utf-8"));

describe("F6 operation status machine", () => {
  for (const t of m.transitions) {
    it(`given ${t.from} when ${t.role} does ${t.action} then ${t.to}`, () => {
      expect(nextStatus(t.from, t.action, t.role)).toBe(t.to);
    });
  }
  for (const i of m.initial) {
    it(`given a ${i.role} creating on ${i.performed_on} then status is ${i.status}`, () => {
      expect(initialStatus(i.performed_on, m.today, i.role)).toBe(i.status);
    });
  }
  for (const o of m.overdue) {
    it(`given ${o.status} on ${o.performed_on} then overdue is ${o.overdue}`, () => {
      expect(isOverdue(o.status, o.performed_on, m.today)).toBe(o.overdue);
    });
  }
});

describe("F6 planned operations (R4-A1, R4-A4)", () => {
  it("given a future date when creating then the status is planned for every role", () => {
    for (const role of ["owner", "manager", "worker"]) expect(initialStatus("2026-12-31", "2026-11-07", role)).toBe("planned");
  });
  it("given a planned operation past its date then it is overdue, derived and never stored", () => {
    expect(isOverdue("planned", "2026-11-06", "2026-11-07")).toBe(true);
    expect(isOverdue("planned", "2026-11-07", "2026-11-07")).toBe(false);
    expect(isOverdue("cancelled", "2026-11-06", "2026-11-07")).toBe(false);
  });
  it("given an overdue planned operation when rescheduling then it stays planned for any role", () => {
    for (const role of ["owner", "manager", "worker"]) expect(nextStatus("planned", "reschedule", role)).toBe("planned");
  });
  it("given a done or cancelled operation when rescheduling then it is refused", () => {
    for (const from of ["done", "validated", "pending_validation", "cancelled"]) expect(nextStatus(from, "reschedule", "owner")).toBeNull();
  });
  it("given a new date in the future when rescheduling then the date moves and it is no longer overdue", () => {
    expect(reschedule({ status: "planned", performed_on: "2026-11-01" }, "2026-11-10", "2026-11-07")).toEqual({
      status: "planned",
      performed_on: "2026-11-10",
    });
  });
  it("given a past date when rescheduling then it throws because a planned date must be in the future", () => {
    expect(() => reschedule({ status: "planned", performed_on: "2026-11-01" }, "2026-11-06", "2026-11-07")).toThrow(/future/);
  });
  it("given a non planned operation when rescheduling then it throws", () => {
    expect(() => reschedule({ status: "validated", performed_on: "2026-11-01" }, "2026-11-10", "2026-11-07")).toThrow(/planned/);
  });
  it("given a planned operation when marking done as a worker then it awaits validation, as staff it is validated", () => {
    expect(nextStatus("planned", "mark_done", "worker")).toBe("pending_validation");
    expect(nextStatus("planned", "mark_done", "manager")).toBe("validated");
  });
});
