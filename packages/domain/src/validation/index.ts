import type { ZodType } from "zod";
import { FarmCreate } from "../schemas/farm";
import { ParcelCreate } from "../schemas/parcel";
import { TrialRecordCreate } from "../schemas/trial_record";

export type ValidationError = { field: string; code: string };
export type Verdict = { valid: boolean; errors: ValidationError[] };

export const RULES: Record<string, ZodType> = {
  "trial_record.create": TrialRecordCreate,
  "parcel.create": ParcelCreate,
  "farm.create": FarmCreate,
};

function valueAt(input: unknown, path: PropertyKey[]): unknown {
  let cur: any = input;
  for (const key of path) {
    if (cur === null || typeof cur !== "object") return undefined;
    cur = cur[key as string];
  }
  return cur;
}

export function validate(rule: string, input: unknown): Verdict {
  const schema = RULES[rule];
  if (!schema) throw new Error(`unknown rule: ${rule}`);
  const result = schema.safeParse(input);
  if (result.success) return { valid: true, errors: [] };

  const seen = new Set<string>();
  const errors: ValidationError[] = [];
  for (const issue of result.error.issues) {
    const field = String(issue.path[0] ?? "");
    let code: string;
    if (issue.code === "invalid_type" && valueAt(input, issue.path) === undefined) {
      code = "required";
    } else if (field === "geometry") {
      code = "invalid_geometry";
    } else if (issue.code === "too_small") {
      code = issue.origin === "string" ? "too_short" : "out_of_range";
    } else if (issue.code === "too_big") {
      code = issue.origin === "string" ? "too_long" : "out_of_range";
    } else {
      code = "invalid";
    }
    const key = `${field}:${code}`;
    if (!seen.has(key)) {
      seen.add(key);
      errors.push({ field, code });
    }
  }
  return { valid: false, errors };
}
