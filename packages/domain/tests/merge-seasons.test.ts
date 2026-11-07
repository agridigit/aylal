import { describe, expect, it } from "vitest";
import { mergeFields } from "../src/merge";
import { square } from "./_f2";

const A = { id: "A", ring: square(-7.6, 33.57, 0.001) };
const B = { id: "B", ring: square(-7.6 + 0.001, 33.57, 0.001) };
const C = { id: "C", ring: square(-7.5, 33.57, 0.001) };
const S = (id: string, field_id: string, crop_id: string, started_at: string, ended_at: string | null = null) => ({ id, field_id, crop_id, started_at, ended_at });

describe("mergeFields seasons and contiguity (R5-A2, CL)", () => {
  it("given two contiguous fields and a distant third when merging all then merge_not_contiguous", () => {
    expect((mergeFields(A, [B, C], []) as any).code).toBe("merge_not_contiguous");
  });
  it("given the oldest same-crop active season on the merged field when merging then it is the one kept", () => {
    const r: any = mergeFields(A, [B], [S("new", "A", "wheat", "2026-01-01"), S("old", "B", "wheat", "2025-01-01")]);
    expect(r.keptSeasonIds).toEqual(["old"]);
    expect(r.droppedSeasonIds).toEqual(["new"]);
  });
  it("given closed seasons of the same crop on both fields when merging then all are kept", () => {
    const r: any = mergeFields(A, [B], [S("c1", "A", "wheat", "2024-01-01", "2024-06-01"), S("c2", "B", "wheat", "2024-01-01", "2024-06-01"), S("act", "B", "wheat", "2025-01-01")]);
    expect([...r.keptSeasonIds].sort()).toEqual(["act", "c1", "c2"]);
    expect(r.droppedSeasonIds).toEqual([]);
  });
  it("given different active crops on each field when merging then both stay active (intercropping)", () => {
    const r: any = mergeFields(A, [B], [S("a", "A", "olive", "2020-01-01"), S("b", "B", "wheat", "2025-01-01")]);
    expect([...r.keptSeasonIds].sort()).toEqual(["a", "b"]);
  });
  it("given a single field when merging then merge_needs_two_fields", () => {
    expect((mergeFields(A, [], []) as any).code).toBe("merge_needs_two_fields");
  });
});
