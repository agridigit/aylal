import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { flattenKeys } from "../src/index";

const LOCALES = ["ary", "ar", "fr"];
const load = (l: string, n: string) => flattenKeys(JSON.parse(readFileSync(join(__dirname, "..", "locales", l, `${n}.json`), "utf8")));
const CROSSING = ["self_intersection", "too_few_vertices", "too_many_vertices", "area_too_small", "area_too_large", "outside_morocco", "field_limit_reached", "invalid_coordinates", "not_a_polygon"];
const REQUIRED: Record<string, string[]> = {
  fields: [
    "draw.taps", "draw.gps", "draw.undo", "draw.close", "draw.crossing_help",
    "gps.precision.good", "gps.precision.medium", "gps.precision.poor", "gps.accuracy",
    ...CROSSING.map((c) => `errors.${c}`),
    "errors.block_outside_field", "errors.block_overlap", "errors.merge_not_contiguous",
  ],
  seasons: ["errors.season_already_active", "start", "close", "history"],
  crops: [],
};
const SLUGS = ["durum-wheat", "olive"];

describe("F2 i18n keys exist and are filled in ary, ar and fr (T030, T068)", () => {
  for (const [ns, keys] of Object.entries(REQUIRED))
    for (const l of LOCALES)
      it(`Given ${l}/${ns}.json, When reading the required keys, Then each is a non-empty string`, () => {
        const flat = load(l, ns);
        const bad = keys.filter((k) => !(flat[k] ?? "").trim());
        expect(bad, `${l}:${ns}`).toEqual([]);
      });

  for (const l of LOCALES)
    it(`Given ${l}/crops.json, When looking up the reference crops, Then each slug has a name`, () => {
      const flat = load(l, "crops");
      expect(SLUGS.filter((s) => !(flat[`names.${s}`] ?? "").trim()), l).toEqual([]);
    });

  it("Given the three locales of fields and crops, When comparing key sets, Then they are identical and not empty", () => {
    for (const ns of ["fields", "crops", "seasons"]) {
      const ref = Object.keys(load("fr", ns)).sort();
      expect(ref.length, ns).toBeGreaterThan(0);
      for (const l of LOCALES) expect(Object.keys(load(l, ns)).sort(), `${l}:${ns}`).toEqual(ref);
    }
  });
});
