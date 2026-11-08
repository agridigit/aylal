import { describe, expect, it } from "vitest";
import * as roles from "../../src/roles";
import { load } from "./_f8";

type RoleRow = { role: string; action: string; allowed: boolean };
const matrix = load<RoleRow>("f8_roles.json");

describe("F8 rights matrix (G1, vectors/f8_roles.json)", () => {
  for (const m of matrix) {
    it(`given role ${m.role} when doing ${m.action} then allowed is ${m.allowed}`, () => {
      expect(roles.can(m.role, m.action)).toBe(m.allowed);
    });
  }
  it("given the worker then no financial action is allowed and harvest.write is (R3-A6, FR-014)", () => {
    const fin = matrix.filter((m) => /^(expense|sale|economics|stock|market_price|receipt)\./.test(m.action) && m.role === "worker");
    expect(fin.length).toBeGreaterThan(10);
    expect(fin.every((m) => !roles.can("worker", m.action))).toBe(true);
    expect(roles.can("worker", "harvest.write")).toBe(true);
    expect(roles.can("worker", "harvest.correct")).toBe(false);
  });
  it("given earlier matrices then they are unchanged", () => {
    expect(roles.can("owner", "farm.delete")).toBe(true);
    expect(roles.can("manager", "farm.delete")).toBe(false);
    expect(roles.can("worker", "finance.read")).toBe(false);
  });
});
