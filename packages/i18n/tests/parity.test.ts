import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { flattenKeys } from "../src/index";

const NAMESPACES = ["auth", "onboarding", "farm", "team", "account", "fields", "crops", "seasons", "map", "operations", "phyto", "registry", "reminders", "dashboard", "weather", "alerts", "vigor", "zones", "status", "summary", "irrigation", "advice", "waterbalance", "wateranalysis", "expenses", "harvests", "economics", "stock", "marketprices"];
const LOCALES = ["ary", "ar", "fr"];
const load = (l: string, n: string) =>
  JSON.parse(readFileSync(join(__dirname, "..", "locales", l, `${n}.json`), "utf8"));

describe("F1/F2 namespace key parity", () => {
  for (const n of NAMESPACES)
    it(`Given namespace ${n}, When comparing locales, Then keys are identical`, () => {
      const ref = Object.keys(flattenKeys(load("fr", n))).sort();
      for (const l of LOCALES) expect(Object.keys(flattenKeys(load(l, n))).sort(), `${l}:${n}`).toEqual(ref);
    });
});

describe("F3 displayed vocabulary (R3-A4)", () => {
  for (const l of LOCALES)
    it(`Given locale ${l}, When scanning F3 namespaces, Then NDVI/NDMI never appear`, () => {
      for (const n of ["dashboard", "weather", "alerts", "vigor", "zones", "status", "summary"])
        expect(JSON.stringify(load(l, n)), `${l}:${n}`).not.toMatch(/ndvi|ndmi/i);
    });
});
