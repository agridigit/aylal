import { readFileSync } from "node:fs";
import { expect, it } from "vitest";

export interface Vec {
  name: string;
  fn: string;
  input: Record<string, unknown>;
  expected: unknown;
  tol?: number;
  exact?: boolean;
}

export function vectors(file: string): Vec[] {
  const raw = JSON.parse(readFileSync(new URL(`../vectors/${file}`, import.meta.url), "utf-8"));
  return Array.isArray(raw) ? raw : raw.cases;
}

export function rawVectors(file: string): any {
  return JSON.parse(readFileSync(new URL(`../vectors/${file}`, import.meta.url), "utf-8"));
}

const camel = (s: string) => s.replace(/_([a-z0-9])/g, (_, c: string) => c.toUpperCase());

/** `expected` is a subset of `actual` (numbers within `tol`, default 0.01) unless `exact`. */
export function matches(actual: unknown, expected: unknown, tol = 0.01, exact = false, path = "$"): void {
  if (typeof expected === "number") {
    expect(typeof actual, path).toBe("number");
    expect(Math.abs((actual as number) - expected), `${path}: ${actual} vs ${expected}`).toBeLessThanOrEqual(tol);
  } else if (Array.isArray(expected)) {
    expect(Array.isArray(actual), path).toBe(true);
    expect((actual as unknown[]).length, path).toBe(expected.length);
    expected.forEach((e, i) => matches((actual as unknown[])[i], e, tol, exact, `${path}[${i}]`));
  } else if (expected !== null && typeof expected === "object") {
    expect(actual !== null && typeof actual === "object", path).toBe(true);
    if (exact) expect(Object.keys(actual as object).sort(), path).toEqual(Object.keys(expected).sort());
    for (const [k, e] of Object.entries(expected)) matches((actual as any)[k], e, tol, exact, `${path}.${k}`);
  } else {
    expect(actual === undefined ? null : actual, path).toEqual(expected);
  }
}

/** One `it` per vector: the module function (camelCase of `fn`) takes the input object and returns an object. */
export function runVectors(mod: Record<string, unknown>, file: string, only?: string[]): void {
  for (const v of vectors(file)) {
    if (only && !only.includes(v.fn)) continue;
    it(`given ${v.name} then ${v.fn} matches the shared vector`, () => {
      const f = mod[camel(v.fn)] as ((i: unknown) => unknown) | undefined;
      expect(typeof f, `export ${camel(v.fn)}`).toBe("function");
      matches(f!(structuredClone(v.input)), v.expected, v.tol ?? 0.01, v.exact ?? false);
    });
  }
}
