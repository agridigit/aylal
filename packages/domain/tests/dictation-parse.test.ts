import { readFileSync } from "node:fs";
import { describe, expect, it, vi } from "vitest";
import { MAX_DICTATION_CHARS, parseDictation, startDictation } from "../src/dictation-parse";

const v = JSON.parse(readFileSync(new URL("../vectors/f6_dictation.json", import.meta.url), "utf-8"));

describe("F6 dictation parsing (R5-A1 to R5-A4): a draft is proposed, never recorded", () => {
  for (const c of v.cases) {
    it(`given ${c.name} when parsing then the draft and the ambiguous fields match the vector`, () => {
      expect(parseDictation(c.text, { parcels: c.parcels, today: v.today })).toEqual(c.expected);
    });
  }

  it("given an ambiguous parcel when parsing then it is flagged and never guessed", () => {
    const c = v.cases[1];
    const out = parseDictation(c.text, { parcels: c.parcels, today: v.today });
    expect(out.draft).not.toHaveProperty("parcel_ids");
    expect(out.ambiguous.map((a: { field: string }) => a.field)).toEqual(["parcel_ids"]);
  });

  it("given a sentence that is not understood when parsing then the form stays empty so icon entry remains possible", () => {
    const out = parseDictation("bla bla xyz", { parcels: [], today: v.today });
    expect(out).toEqual({ understood: false, requires_confirmation: true, draft: {}, ambiguous: [] });
  });

  it("given a text over the maximum length when parsing then it is not understood and nothing is analysed", () => {
    expect(MAX_DICTATION_CHARS).toBe(500);
    const out = parseDictation("j'ai traité " + "x".repeat(MAX_DICTATION_CHARS), { parcels: [], today: v.today });
    expect(out.understood).toBe(false);
  });

  it("given any input when parsing then the result always requires a confirmation", () => {
    for (const c of v.cases) expect(parseDictation(c.text, { parcels: c.parcels, today: v.today }).requires_confirmation).toBe(true);
  });

  it("given a dictation that is not confirmed when the session ends then nothing is saved", async () => {
    const save = vi.fn();
    const c = v.cases[0];
    const flow = startDictation(c.text, { parcels: c.parcels, today: v.today }, save);
    expect(flow.result.understood).toBe(true);
    expect(save).not.toHaveBeenCalled();
    flow.cancel();
    expect(save).not.toHaveBeenCalled();
    await expect(flow.confirm({})).rejects.toThrow();
    expect(save).not.toHaveBeenCalled();
  });

  it("given a confirmation with the farmer's choices when confirming then the draft completed by the farmer is saved once", async () => {
    const save = vi.fn().mockResolvedValue({ id: "op-1" });
    const c = v.cases[1];
    const flow = startDictation(c.text, { parcels: c.parcels, today: v.today }, save);
    await flow.confirm({ parcel_ids: ["p-bas"] });
    expect(save).toHaveBeenCalledTimes(1);
    expect(save.mock.calls[0]?.[0]).toMatchObject({ type: "phyto", parcel_ids: ["p-bas"] });
    await expect(flow.confirm({ parcel_ids: ["p-bas"] })).rejects.toThrow();
    expect(save).toHaveBeenCalledTimes(1);
  });

  it("given an ambiguous field left unresolved when confirming then the save is refused", async () => {
    const save = vi.fn();
    const c = v.cases[1];
    const flow = startDictation(c.text, { parcels: c.parcels, today: v.today }, save);
    await expect(flow.confirm({})).rejects.toThrow();
    expect(save).not.toHaveBeenCalled();
  });
});
