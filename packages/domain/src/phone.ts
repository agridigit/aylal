import { z } from "zod";

const LOCAL = /^0([67]\d{8})$/;
const INTL = /^\+212([67]\d{8})$/;

/** Normalise a Moroccan mobile number to E.164 (+2126/7xxxxxxxx), or null when invalid. */
export function normalizePhone(input: string): string | null {
  const compact = input.replace(/[\s-]/g, "");
  const canonical = compact.startsWith("00212") ? `+${compact.slice(2)}` : compact;
  const match = LOCAL.exec(canonical) ?? INTL.exec(canonical);
  if (!match) return null;
  return `+212${match[1]}`;
}

export const PhoneInput = z
  .object({ phone: z.string().refine((p) => normalizePhone(p) !== null, { message: "invalid_phone" }) })
  .meta({ title: "PhoneInput" });
