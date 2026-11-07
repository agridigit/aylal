import { buildHomeViewModel } from "../homeViewModel";
import { MIN_TOUCH_TARGET_DP } from "../direction";

describe("Home touch targets (AC2.5, FR-010)", () => {
  it("Given the minimum, Then it is 48 dp", () => {
    expect(MIN_TOUCH_TARGET_DP).toBe(48);
  });

  it("Given any Home state, When listing buttons, Then each is at least 48 dp in both dimensions", () => {
    for (const isLoading of [true, false])
      for (const error of [null, new Error("e")])
        for (const itemCount of [0, 5]) {
          const vm = buildHomeViewModel({ isLoading, error, isOffline: false, itemCount });
          for (const b of vm.buttons) {
            expect(b.minWidth, b.id).toBeGreaterThanOrEqual(48);
            expect(b.minHeight, b.id).toBeGreaterThanOrEqual(48);
          }
        }
  });

  it("Given the Home screen, When listing buttons, Then the 4 language choices and the voice button are present", () => {
    const ids = buildHomeViewModel({ isLoading: false, error: null, isOffline: false, itemCount: 1 }).buttons.map((b) => b.id);
    for (const id of ["lang.ary", "lang.ary-Latn", "lang.ar", "lang.fr", "home.speak"]) expect(ids).toContain(id);
  });
});
