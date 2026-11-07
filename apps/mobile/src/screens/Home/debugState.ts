export type DebugState = "error" | "loading";

/** Test-only override of the home state (Maestro deep link). Disabled unless the build enables E2E debug. */
export function debugStateFrom(param: string | string[] | undefined, e2eEnabled: boolean): DebugState | null {
  if (!e2eEnabled) return null;
  const value = Array.isArray(param) ? param[0] : param;
  return value === "error" || value === "loading" ? value : null;
}
