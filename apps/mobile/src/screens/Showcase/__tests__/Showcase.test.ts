import { buildShowcase } from "../showcaseViewModel";

describe("Showcase animated screen (AC6.3, FR-024)", () => {
  it("Given animations enabled, When building, Then animated items have a positive duration", () => {
    const vm = buildShowcase({ reduceMotion: false });
    expect(vm.animations.length).toBeGreaterThan(0);
    for (const a of vm.animations) expect(a.durationMs).toBeGreaterThan(0);
  });

  it("Given reduce animations is on, When building, Then no animation runs and the final state is shown", () => {
    const vm = buildShowcase({ reduceMotion: true });
    for (const a of vm.animations) expect(a.durationMs).toBe(0);
    expect(vm.animated).toBe(false);
  });

  it("Given the showcase, When listing components, Then they come from packages/ui only", () => {
    expect(buildShowcase({ reduceMotion: false }).components.every((c) => c.source === "@aylal/ui")).toBe(true);
  });
});
