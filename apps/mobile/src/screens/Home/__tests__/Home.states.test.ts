import { buildHomeViewModel, deriveHomeState } from "../homeViewModel";

const base = { isLoading: false, error: null, isOffline: false, itemCount: 3 };

describe("Home 4 states (AC2.4, FR-009)", () => {
  it("Given data loading, When deriving, Then the skeleton state is shown", () => {
    const vm = buildHomeViewModel({ ...base, isLoading: true });
    expect(vm.state).toBe("loading");
    expect(vm.blocks.map((b) => b.component)).toContain("Skeleton");
  });

  it("Given no data, When deriving, Then the empty state has an illustration and an action", () => {
    const vm = buildHomeViewModel({ ...base, itemCount: 0 });
    expect(vm.state).toBe("empty");
    const b = vm.blocks.find((x) => x.component === "EmptyState");
    expect(b?.messageKey).toBeTruthy();
    expect(b?.illustration).toBeTruthy();
    expect(b?.action?.labelKey).toBeTruthy();
  });

  it("Given an error, When deriving, Then a message and a solution with retry are shown", () => {
    const vm = buildHomeViewModel({ ...base, error: new Error("x") });
    expect(vm.state).toBe("error");
    const b = vm.blocks.find((x) => x.component === "ErrorState");
    expect(b?.messageKey).toBeTruthy();
    expect(b?.solutionKey).toBeTruthy();
    expect(b?.action?.labelKey).toBeTruthy();
  });

  it("Given no network, When deriving, Then the offline indicator is visible and content stays", () => {
    const vm = buildHomeViewModel({ ...base, isOffline: true });
    expect(vm.showOfflineBanner).toBe(true);
    expect(vm.blocks.map((b) => b.component)).toContain("OfflineBanner");
    expect(vm.state).toBe("ready");
  });

  it("Given online with data, When deriving, Then no offline indicator", () => {
    expect(buildHomeViewModel(base).showOfflineBanner).toBe(false);
  });

  it("Given any input combination, When deriving, Then the screen is never blank", () => {
    for (const isLoading of [true, false])
      for (const error of [null, new Error("e")])
        for (const isOffline of [true, false])
          for (const itemCount of [0, 5]) {
            const vm = buildHomeViewModel({ isLoading, error, isOffline, itemCount });
            expect(vm.blocks.length, JSON.stringify({ isLoading, isOffline, itemCount })).toBeGreaterThan(0);
          }
  });

  it("Given loading and error together, When deriving, Then loading wins; error beats empty", () => {
    expect(deriveHomeState({ ...base, isLoading: true, error: new Error("e") })).toBe("loading");
    expect(deriveHomeState({ ...base, error: new Error("e"), itemCount: 0 })).toBe("error");
  });
});
