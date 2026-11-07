import { describe, expect, it } from "vitest";
import { catalog } from "../src/components/catalog";
import { tokens } from "../src/tokens";

describe("touch targets", () => {
  it("Given the interactive components, When listed, Then Button, TextField, Switch and ListItem are interactive", () => {
    const names = catalog.filter((c) => c.interactive).map((c) => c.name);
    for (const n of ["Button", "TextField", "Switch", "ListItem"]) expect(names).toContain(n);
  });

  it("Given any interactive component, When reading its touch area, Then it is at least 48 dp", () => {
    for (const c of catalog.filter((c) => c.interactive)) {
      expect(c.minTouchTarget, c.name).toBeGreaterThanOrEqual(48);
      expect(c.minTouchTarget, c.name).toBeGreaterThanOrEqual(tokens.touchTargetMin);
    }
  });
});
