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

import { INVITABLE_ROLES, canAssignParcelsTo, canRemoveMember } from "../src/roles";

describe("role rules beyond the matrix (R6-A2, FR-022)", () => {
  it("given the invitable roles then owner is never one of them", () => {
    expect([...INVITABLE_ROLES]).toEqual(["manager", "worker"]);
  });
  const remove: [string, string, boolean][] = [
    ["owner", "manager", true], ["owner", "worker", true], ["owner", "owner", false],
    ["manager", "worker", false], ["manager", "manager", false], ["worker", "worker", false],
  ];
  for (const [actor, target, ok] of remove) {
    it(`given ${actor} when removing ${target} then allowed is ${ok}`, () => {
      expect(canRemoveMember(actor, target)).toBe(ok);
    });
  }
  const assign: [string, string, boolean][] = [
    ["owner", "worker", true], ["manager", "worker", true], ["worker", "worker", false],
    ["owner", "manager", false], ["manager", "owner", false],
  ];
  for (const [actor, target, ok] of assign) {
    it(`given ${actor} when assigning parcels to ${target} then allowed is ${ok}`, () => {
      expect(canAssignParcelsTo(actor, target)).toBe(ok);
    });
  }
});

describe("F2 roles matrix shared vectors (field.*, season.*, crop.create_custom)", () => {
  const f2: { role: string; action: string; allowed: boolean }[] = JSON.parse(
    readFileSync(new URL("../vectors/f2_roles.json", import.meta.url), "utf-8"),
  );
  for (const m of f2) {
    it(`given role ${m.role} when doing ${m.action} then allowed is ${m.allowed}`, () => {
      expect(can(m.role, m.action)).toBe(m.allowed);
    });
  }
  it("given an unknown F2 action then nobody can do it", () => {
    expect(can("owner", "field.teleport")).toBe(false);
  });
});
