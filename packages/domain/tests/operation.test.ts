import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { initialStatus, isOverdue, nextStatus } from "../src/operation";

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
