import { applyLocaleDirection, directionalIcon, layoutFor } from "../direction";

const manager = (isRTL: boolean) => {
  const calls: string[] = [];
  return {
    isRTL,
    calls,
    allowRTL: (v: boolean) => calls.push(`allow:${v}`),
    forceRTL: (v: boolean) => calls.push(`force:${v}`),
  };
};

describe("Home RTL (AC2.3, FR-008)", () => {
  it.each(["ar", "ary"] as const)("Given %s in Arabic script, When laying out, Then it is fully mirrored", (l) => {
    expect(layoutFor(l)).toMatchObject({ isRTL: true, writingDirection: "rtl", textAlign: "right", mirrorIcons: true });
  });

  it.each(["ary-Latn", "fr"] as const)("Given %s, When laying out, Then it is LTR", (l) => {
    expect(layoutFor(l)).toMatchObject({ isRTL: false, writingDirection: "ltr", textAlign: "left", mirrorIcons: false });
  });

  it("Given an RTL locale and an LTR runtime, When applying, Then RTL is forced and a reload is required", () => {
    const m = manager(false);
    expect(applyLocaleDirection("ar", m)).toEqual({ isRTL: true, reloadRequired: true });
    expect(m.calls).toEqual(["allow:true", "force:true"]);
  });

  it("Given an RTL runtime and fr, When applying, Then LTR is forced and a reload is required", () => {
    const m = manager(true);
    expect(applyLocaleDirection("fr", m)).toEqual({ isRTL: false, reloadRequired: true });
    expect(m.calls).toContain("force:false");
  });

  it("Given the runtime already matches, When applying, Then no reload is required", () => {
    expect(applyLocaleDirection("ary", manager(true)).reloadRequired).toBe(false);
    expect(applyLocaleDirection("ary-Latn", manager(false)).reloadRequired).toBe(false);
  });

  it("Given a directional icon, When RTL, Then it is mirrored; otherwise unchanged", () => {
    expect(directionalIcon("chevron-forward", true)).toBe("chevron-back");
    expect(directionalIcon("chevron-back", true)).toBe("chevron-forward");
    expect(directionalIcon("chevron-forward", false)).toBe("chevron-forward");
    expect(directionalIcon("play", true)).toBe("play");
  });
});
