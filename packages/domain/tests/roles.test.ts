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

describe("F6 roles matrix shared vectors (operation.*, registry.*, phyto_product.create_free)", () => {
  const f6: { role: string; action: string; allowed: boolean }[] = JSON.parse(
    readFileSync(new URL("../vectors/f6_roles.json", import.meta.url), "utf-8"),
  );
  for (const m of f6) {
    it(`given role ${m.role} when doing ${m.action} then allowed is ${m.allowed}`, () => {
      expect(can(m.role, m.action)).toBe(m.allowed);
    });
  }
  it("given any role then physical deletion of an operation is never allowed", () => {
    expect(ROLES.some((r) => can(r, "operation.delete"))).toBe(false);
  });
});

const f3: { role: string; action: string; allowed: boolean }[] = JSON.parse(
  readFileSync(new URL("../vectors/f3_roles.json", import.meta.url), "utf-8"),
);

describe("F3 monitoring rights (G1)", () => {
  for (const m of f3) {
    it(`given role ${m.role} when doing ${m.action} then allowed is ${m.allowed}`, () => {
      expect(can(m.role, m.action)).toBe(m.allowed);
    });
  }
  it("given the F3 actions then none is a financial action", () => {
    expect(f3.filter((m) => /finance|price|cost|amount/.test(m.action))).toEqual([]);
  });
});

const f4: { role: string; action: string; allowed: boolean }[] = JSON.parse(
  readFileSync(new URL("../vectors/f4_roles.json", import.meta.url), "utf-8"),
);

describe("F4 irrigation rights (G1)", () => {
  for (const m of f4) {
    it(`given role ${m.role} when doing ${m.action} then allowed is ${m.allowed}`, () => {
      expect(can(m.role, m.action)).toBe(m.allowed);
    });
  }
  it("given the worker then water analyses are never readable nor writable", () => {
    expect(can("worker", "water_analysis.read")).toBe(false);
    expect(can("worker", "water_analysis.write")).toBe(false);
  });
  it("given the F4 actions then none is a financial action and nobody can ingest moisture through a route", () => {
    expect(f4.filter((m) => /finance|price|cost|amount/.test(m.action))).toEqual([]);
    expect(ROLES.some((r) => can(r, "moisture.ingest"))).toBe(false);
  });
});
