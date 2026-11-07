import { z } from "zod";
import { validateWith, type Verdict } from "./validation/verdict";

export const LANGUAGES = ["ary", "ar", "fr"] as const;

export const ProfileUpdate = z
  .object({ display_name: z.string().trim().min(1).max(80), language: z.enum(LANGUAGES) })
  .meta({ title: "ProfileUpdate" });

export const PROFILE_FIELDS = ["display_name", "language"] as const;

/** Data minimisation: any field outside PROFILE_FIELDS is refused. */
export function validateProfile(input: unknown): Verdict {
  const base = validateWith(ProfileUpdate, input);
  const extras =
    input !== null && typeof input === "object"
      ? Object.keys(input).filter((k) => !(PROFILE_FIELDS as readonly string[]).includes(k))
      : [];
  if (extras.length === 0) return base;
  return { valid: false, errors: [...base.errors, ...extras.map((field) => ({ field, code: "unknown_field" }))] };
}

export type OnboardingProgress = {
  language: string | null;
  phoneVerified: boolean;
  consentGiven: boolean;
  displayName: string | null;
  hasFarm: boolean;
};
export type OnboardingStep = "language" | "phone" | "consent" | "profile" | "farm" | "done";

/** Fixed order: language, phone, consent (before any profile data), profile, farm. */
export function nextOnboardingStep(p: OnboardingProgress): OnboardingStep {
  if (!p.language) return "language";
  if (!p.phoneVerified) return "phone";
  if (!p.consentGiven) return "consent";
  if (!p.displayName) return "profile";
  if (!p.hasFarm) return "farm";
  return "done";
}
