import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { composeSummary, orderSummary } from "../src/voice-summary";

const v: { name: string; parcels: { parcel_id: string; color: string; reason_key: string }[]; expected: string[] }[] = JSON.parse(
  readFileSync(new URL("../vectors/f3_summary.json", import.meta.url), "utf-8"),
);

describe("F3 voice summary order (FR-016)", () => {
  for (const c of v) {
    it(`given ${c.name} then the order matches`, () => {
      expect(orderSummary(c.parcels).map((p) => p.parcel_id)).toEqual(c.expected);
    });
  }
});

const parcels = [
  { parcel_id: "g", color: "green", reason_key: "status.nothing_to_do" },
  { parcel_id: "o1", color: "orange", reason_key: "status.watch" },
  { parcel_id: "r1", color: "red", reason_key: "status.frost" },
  { parcel_id: "hidden", color: "red", reason_key: "status.secret" },
];
const keys = (s: { segments: { key: string }[] }) => s.segments.map((x) => x.key);

describe("F3 voice summary composition (R7-A1, R7-A2)", () => {
  it("given red and orange parcels and the weather then red come first, then orange, then the weather of the day", () => {
    const s = composeSummary({ items: parcels, weatherCode: "sun", locale: "fr", visibleParcelIds: ["g", "o1", "r1"] });
    expect(keys(s)).toEqual(["summary.intro", "summary.red", "summary.orange", "summary.weather"]);
    expect(s.segments.filter((x) => x.key === "summary.red" || x.key === "summary.orange").map((x) => x.parcelId)).toEqual(["r1", "o1"]);
  });
  it.each(["ary", "ar", "fr"] as const)("given the recipient language %s then the summary is generated in that language", (locale) => {
    expect(composeSummary({ items: parcels, weatherCode: "sun", locale, visibleParcelIds: ["r1"] }).locale).toBe(locale);
  });
  it("given an unknown language then the summary falls back to French", () => {
    expect(composeSummary({ items: parcels, weatherCode: "sun", locale: "de", visibleParcelIds: ["r1"] }).locale).toBe("fr");
  });
  it("given a parcel outside the recipient scope then it is never part of the summary", () => {
    const s = composeSummary({ items: parcels, weatherCode: "sun", locale: "fr", visibleParcelIds: ["r1", "o1"] });
    expect(JSON.stringify(s)).not.toContain("hidden");
  });
  it("given an empty scope then nothing about any parcel is said", () => {
    const s = composeSummary({ items: parcels, weatherCode: "sun", locale: "fr", visibleParcelIds: [] });
    expect(keys(s)).toEqual(["summary.intro", "summary.nothing_to_watch", "summary.weather"]);
  });
  it("given no weather then the weather is said to be unavailable and no code is invented", () => {
    const s = composeSummary({ items: parcels, weatherCode: null, locale: "fr", visibleParcelIds: ["r1"] });
    expect(keys(s).at(-1)).toBe("summary.weather_unavailable");
    expect(JSON.stringify(s)).not.toMatch(/null|undefined/);
  });
  it("given any summary then it is made of i18n keys only, never of literal text", () => {
    const s = composeSummary({ items: parcels, weatherCode: "sun", locale: "ary", visibleParcelIds: ["g", "o1", "r1"] });
    for (const x of s.segments) expect(x.key).toMatch(/^summary\.[a-z_]+$/);
  });
});
