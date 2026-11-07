import { readdirSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { LOCALES } from "../../src/index";

describe("i18n locale files on disk (AC2.2)", () => {
  it("Given the locales directory, When listing it, Then it holds exactly one file per supported locale", () => {
    const files = readdirSync(join(__dirname, "..", "..", "locales")).filter((f) => f.endsWith(".json"));
    expect(files.map((f) => f.replace(/\.json$/, "")).sort()).toEqual([...LOCALES].sort());
  });
});
