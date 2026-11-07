import type { ZodType } from "zod";
import { ConsentGrant } from "../consent";
import { FarmRegistration } from "../farm";
import { ProfileUpdate } from "../onboarding";
import { PhoneInput } from "../phone";
import { FarmCreate } from "../schemas/farm";
import { ParcelCreate } from "../schemas/parcel";
import { TrialRecordCreate } from "../schemas/trial_record";
import { validateWith, type ValidationError, type Verdict } from "./verdict";

export type { ValidationError, Verdict };


export const RULES: Record<string, ZodType> = {
  "trial_record.create": TrialRecordCreate,
  "parcel.create": ParcelCreate,
  "farm.create": FarmCreate,
  phone: PhoneInput,
  farm: FarmRegistration,
  consent: ConsentGrant,
  profile: ProfileUpdate,
};

export function validate(rule: string, input: unknown): Verdict {
  const schema = RULES[rule];
  if (!schema) throw new Error(`unknown rule: ${rule}`);
  return validateWith(schema, input);
}
