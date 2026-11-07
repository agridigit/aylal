import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { tokens } from "../src/tokens";
import Ajv2020 from "ajv/dist/2020";

const schema = JSON.parse(
  readFileSync(new URL("../../../specs/001-foundations/contracts/design-tokens.schema.json", import.meta.url), "utf-8"),
);
const THEMES = ["light", "dark", "sun"] as const;

describe("design tokens contract", () => {
  it("Given the tokens, When validated against design-tokens.schema.json, Then they are valid", () => {
    const ajv = new Ajv2020({ strict: false });
    const validate = ajv.compile(schema);
    expect(validate(tokens), JSON.stringify(validate.errors)).toBe(true);
  });

  for (const theme of THEMES) {
    it(`Given the ${theme} theme, When read, Then it defines every required color role`, () => {
      for (const role of schema.properties.themes.patternProperties["^(light|dark|sun)$"].required) {
        expect(tokens.themes[theme][role]).toMatch(/^#[0-9A-Fa-f]{6}$/);
      }
    });
  }

  it("Given the spacing scale, When read, Then every value is a multiple of 4 px", () => {
    const values = Object.values(tokens.space) as number[];
    expect(values.length).toBeGreaterThan(0);
    for (const v of values) expect(v % 4).toBe(0);
  });

  it("Given the typography, When read, Then fonts are IBM Plex Sans and IBM Plex Sans Arabic", () => {
    expect(tokens.typography.fontFamily).toBe("IBM Plex Sans");
    expect(tokens.typography.fontFamilyArabic).toBe("IBM Plex Sans Arabic");
  });

  it("Given the tokens, When read, Then the minimum touch target is 48 dp", () => {
    expect(tokens.touchTargetMin).toBe(48);
  });
});
