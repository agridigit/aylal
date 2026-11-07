import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { resolveFieldConflicts } from "../src/conflict";

type Vector = { name: string; record: any; op: any; expect: any };

const vectors: Vector[] = JSON.parse(
  readFileSync(new URL("../vectors/conflict.field_merge.json", import.meta.url), "utf-8"),
);

describe("field-by-field conflict resolution by server arrival order", () => {
  for (const v of vectors) {
    it(v.name, () => {
      const out = resolveFieldConflicts(v.record, v.op);
      expect(out.fields).toEqual(v.expect.fields);
      expect(out.field_versions).toEqual(v.expect.field_versions);
      expect(out.server_version).toBe(v.expect.server_version);
      expect(out.has_conflict).toBe(v.expect.has_conflict);
      expect(out.conflicts).toEqual(v.expect.conflicts);
    });
  }

  it("is independent of the device clock", () => {
    const v = vectors.find((x) => x.name.includes("last arrival"))!;
    const a = resolveFieldConflicts(v.record, { ...v.op, device_clock: "1970-01-01T00:00:00Z" });
    const b = resolveFieldConflicts(v.record, { ...v.op, device_clock: "2099-01-01T00:00:00Z" });
    expect(a).toEqual(b);
  });
});
