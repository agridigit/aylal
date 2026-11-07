import { z } from "zod";
import { validateWith, type Verdict } from "./validation/verdict";

export const ConsentGrant = z
  .object({ purpose: z.string().trim().min(1).max(80), text_version: z.string().trim().min(1).max(40) })
  .meta({ title: "ConsentGrant" });

export const validateConsent = (input: unknown): Verdict => validateWith(ConsentGrant, input);

export const CONSENT_PURPOSE_DATA_POLICY = "data_policy";

export type ConsentRecord = { purpose: string; text_version: string; withdrawn_at: string | null };

/** A consent counts only for the current text version and until it is withdrawn. */
export function hasActiveConsent(grants: readonly ConsentRecord[], purpose: string, version: string): boolean {
  return grants.some((g) => g.purpose === purpose && g.text_version === version && !g.withdrawn_at);
}
