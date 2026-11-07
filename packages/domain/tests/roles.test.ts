import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { ROLES, can } from "../src/roles";

const matrix: { role: string; action: string; allowed: boolean }[] = JSON.parse(
  readFileSync(new URL("../vectors/f1_roles.json", import.meta.url), "utf-8"),
);

describe("roles and rights", () => {
  it("given the role set then it is owner, manager, worker", () => {
    expect([...ROLES]).toEqual(["owner", "manager", "worker"]);
  });
  for (const m of matrix) {
    it(`given role ${m.role} when doing ${m.action} then allowed is ${m.allowed}`, () => {
      expect(can(m.role, m.action)).toBe(m.allowed);
    });
  }
});
