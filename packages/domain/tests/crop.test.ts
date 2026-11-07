import { describe, expect, it } from "vitest";
import { REFERENCE_CROP_SLUGS, validateCustomCrop } from "../src/crop";

describe("crop reference", () => {
  it("given the reference list then it has the 16 seeded crops", () => {
    expect([...REFERENCE_CROP_SLUGS].sort()).toEqual(
      ["olive", "citrus", "durum-wheat", "soft-wheat", "barley", "tomato", "potato", "onion", "berries", "avocado",
        "date-palm", "almond", "grape", "sugar-beet", "alfalfa", "silage-maize"].sort(),
    );
  });
});

describe("validateCustomCrop", () => {
  it("given a named custom crop when validating then it carries no agronomy", () => {
    const r: any = validateCustomCrop({ name_fr: "Henné", cycle: "perennial" });
    expect(r.ok).toBe(true);
    expect(r.crop).toMatchObject({ has_agronomy: false, validated: false });
    expect(r.crop.stages ?? []).toEqual([]);
  });
  it("given an empty name or an unknown cycle when validating then it is refused", () => {
    expect((validateCustomCrop({ name_fr: "", cycle: "annual" }) as any).ok).toBe(false);
    expect((validateCustomCrop({ name_fr: "X", cycle: "weekly" }) as any).ok).toBe(false);
  });
});
