import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { OTP_LOCK_SECONDS, OTP_MAX_FAILURES, isLocked, registerFailure } from "../src/otp-policy";

type State = { failedAttempts: number; lockedUntilMs: number | null };
const vectors: {
  name: string;
  state: State;
  action: "failure" | "isLocked";
  nowMs: number;
  expect: State | boolean;
}[] = JSON.parse(readFileSync(new URL("../vectors/f1_otp_policy.json", import.meta.url), "utf-8"));

describe("OTP policy", () => {
  it("given the policy constants then 3 failures lock for 5 minutes", () => {
    expect(OTP_MAX_FAILURES).toBe(3);
    expect(OTP_LOCK_SECONDS).toBe(300);
  });
  for (const v of vectors) {
    it(v.name, () => {
      const got = v.action === "failure" ? registerFailure(v.state, v.nowMs) : isLocked(v.state, v.nowMs);
      expect(got).toEqual(v.expect);
    });
  }
});
