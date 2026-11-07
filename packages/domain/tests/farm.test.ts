import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { validateFarm } from "../src/farm";

type V = { name: string; rule: string; input: unknown; expect: { valid: boolean; errors: { field: string; code: string }[] } };
const vectors: V[] = (JSON.parse(readFileSync(new URL("../vectors/f1_validation.json", import.meta.url), "utf-8")) as V[]).filter(
  (v) => v.rule === "farm",
);
const key = (e: { field: string; code: string }[]) => [...e].map((x) => x.field + ":" + x.code).sort();

describe("farm validation", () => {
  for (const v of vectors) {
    it(v.name, () => {
      const got = validateFarm(v.input);
      expect(got.valid).toBe(v.expect.valid);
      expect(key(got.errors)).toEqual(key(v.expect.errors));
    });
  }
});

import { farmUploadState } from "../src/farm";

describe("farm upload indicator (R4-A3)", () => {
  it("Given a farm created offline and still queued, When reading its state, Then it is pending upload", () => {
    expect(farmUploadState("f1", ["f1", "f2"])).toBe("pending_upload");
  });
  it("Given a farm no longer queued, When reading its state, Then it is synced", () => {
    expect(farmUploadState("f1", ["f2"])).toBe("synced");
  });
});

describe("farm required fields (R4-A1, R4-A5)", () => {
  it("Given a farm with a blank name, When validating, Then name is refused", () => {
    expect(validateFarm({ name: "   ", location: { lat: 33, lon: -7 } }).valid).toBe(false);
  });
  it("Given a farm without area, When validating, Then it is valid", () => {
    expect(validateFarm({ name: "Ferme", location: { lat: 33, lon: -7 } }).valid).toBe(true);
  });
});
