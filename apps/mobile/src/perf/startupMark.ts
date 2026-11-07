export const STARTUP_BUDGET_MS = 3000;

export interface StartupEvent {
  name: "home_displayed";
  durationMs: number;
}

interface Deps {
  now?: () => number;
  emit?: (e: StartupEvent) => void;
}

export function createStartupMark(deps: Deps = {}) {
  const now = deps.now ?? (() => Date.now());
  const emit =
    deps.emit ??
    ((e: StartupEvent) => {
      (globalThis as { performance?: { mark?: (n: string, o?: unknown) => void } }).performance?.mark?.(e.name, { detail: e });
    });
  let started = now();
  let done = false;
  return {
    appStarted() {
      started = now();
    },
    homeDisplayed() {
      if (done) return;
      done = true;
      emit({ name: "home_displayed", durationMs: now() - started });
    },
    withinBudget: (durationMs: number) => durationMs < STARTUP_BUDGET_MS,
  };
}
