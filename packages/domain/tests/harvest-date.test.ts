import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { earliestHarvest } from "../src/harvest-date";

const v = JSON.parse(readFileSync(new URL("../vectors/f6_harvest_date.json", import.meta.url), "utf-8"));

describe("F6 earliest harvest date (R3-A1 to R3-A4)", () => {
  for (const c of v.cases) {
    it(`given ${c.name} when computing then the result matches the vector`, () => {
      expect(earliestHarvest(c.entries, v.today)).toEqual(c.expected);
    });
  }
  it("given entries in any order when computing then the result is the same", () => {
    const c = v.cases[1];
    expect(earliestHarvest([...c.entries].reverse(), v.today)).toEqual(c.expected);
  });
});
