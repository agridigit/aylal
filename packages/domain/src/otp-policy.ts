export const OTP_MAX_FAILURES = 3;
export const OTP_LOCK_SECONDS = 300;

export type OtpState = { failedAttempts: number; lockedUntilMs: number | null };

export function isLocked(state: OtpState, nowMs: number): boolean {
  return state.lockedUntilMs !== null && nowMs < state.lockedUntilMs;
}

export function registerFailure(state: OtpState, nowMs: number): OtpState {
  const failedAttempts = state.failedAttempts + 1;
  const lockedUntilMs = failedAttempts >= OTP_MAX_FAILURES ? nowMs + OTP_LOCK_SECONDS * 1000 : state.lockedUntilMs;
  return { failedAttempts, lockedUntilMs };
}
