import type { ZodType } from "zod";

export type ValidationError = { field: string; code: string };
export type Verdict = { valid: boolean; errors: ValidationError[] };

function valueAt(input: unknown, path: PropertyKey[]): unknown {
  let cur: any = input;
  for (const key of path) {
    if (cur === null || typeof cur !== "object") return undefined;
    cur = cur[key as string];
  }
  return cur;
}

export function validateWith(schema: ZodType, input: unknown): Verdict {
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
    } else if (issue.code === "invalid_value") {
      code = "invalid_choice";
    } else if (issue.code === "too_small") {
      code = issue.origin === "string" ? "too_short" : field === "area_ha" ? "too_small" : "out_of_range";
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
