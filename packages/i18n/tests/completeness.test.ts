import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { assertComplete, flattenKeys, LOCALES } from "../src/index";

const load = (l: string) => JSON.parse(readFileSync(join(__dirname, "..", "locales", `${l}.json`), "utf8"));
const vars = (s: string) => (s.match(/\{\{\s*\w+\s*\}\}/g) ?? []).map((v) => v.replace(/\s/g, "")).sort();

describe("i18n completeness (AC2.2, SC-004)", () => {
  it("Given the contract, When listing locales, Then ary, ary-Latn, ar and fr are supported", () => {
    expect([...LOCALES].sort()).toEqual(["ar", "ary", "ary-Latn", "fr"]);
  });

  it("Given the four locale files, When comparing keys, Then they all have the same keys", () => {
    const ref = Object.keys(flattenKeys(load("fr"))).sort();
    expect(ref.length).toBeGreaterThan(0);
    for (const l of LOCALES) expect(Object.keys(flattenKeys(load(l))).sort(), l).toEqual(ref);
  });

  it("Given the locale files, When reading values, Then none is empty", () => {
    for (const l of LOCALES)
      for (const [k, v] of Object.entries(flattenKeys(load(l)))) expect(v.trim(), `${l}:${k}`).not.toBe("");
  });

  it("Given an interpolated key, When comparing locales, Then the same variables are used", () => {
    const fr = flattenKeys(load("fr"));
    for (const l of LOCALES)
      for (const [k, v] of Object.entries(flattenKeys(load(l)))) expect(vars(v), `${l}:${k}`).toEqual(vars(fr[k]));
  });

  it("Given a missing key in one locale, When asserting completeness, Then the error names the locale and the key", () => {
    const res = { fr: { home: { title: "a", sub: "b" } }, ar: { home: { title: "a" } } };
    expect(() => assertComplete(res, "fr")).toThrow(/ar.*home\.sub|home\.sub.*ar/);
  });

  it("Given an empty value, When asserting completeness, Then the error names the key", () => {
    const res = { fr: { home: { title: "a" } }, ar: { home: { title: " " } } };
    expect(() => assertComplete(res, "fr")).toThrow(/home\.title/);
  });
});
