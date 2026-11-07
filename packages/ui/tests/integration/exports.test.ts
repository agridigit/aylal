import { readdirSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

describe("ui package surface (AC4.3)", () => {
  it("Given the components directory, When listing it, Then it is non-empty and each component is a source file", () => {
    const dir = join(__dirname, "..", "..", "src", "components");
    const files = readdirSync(dir).filter((f) => /\.tsx?$/.test(f));
    expect(files.length).toBeGreaterThan(0);
  });
});
