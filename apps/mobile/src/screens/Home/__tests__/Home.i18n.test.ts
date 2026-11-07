import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { HOME_TEXT_KEYS } from "../keys";
import { resources, LOCALES, flattenKeys } from "@aylal/i18n";

const dir = join(__dirname, "..");
const sources = () => readdirSync(dir).filter((f) => /\.tsx?$/.test(f)).map((f) => [f, readFileSync(join(dir, f), "utf8")] as const);

describe("Home i18n (AC2.2)", () => {
  it("Given the Home screen, When listing its text keys, Then there is at least one", () => {
    expect(HOME_TEXT_KEYS.length).toBeGreaterThan(0);
  });

  it("Given every locale, When reading each Home key, Then it exists and is not empty", () => {
    for (const l of LOCALES) {
      const flat = flattenKeys(resources[l]);
      for (const k of HOME_TEXT_KEYS) expect(flat[k]?.trim(), `${l}:${k}`).toBeTruthy();
    }
  });

  it("Given the Home sources, When scanning for literals, Then no visible hard-coded text exists", () => {
    const files = sources().filter(([f]) => f.endsWith(".tsx"));
    expect(files.length).toBeGreaterThan(0);
    for (const [f, src] of files) {
      expect(src, f).not.toMatch(/>\s*[A-Za-zÀ-ɏ؀-ۿ][^<>{}]*</);
      expect(src, f).not.toMatch(/\b(title|label|placeholder|accessibilityLabel)=["'][^"']+["']/);
    }
  });
});
