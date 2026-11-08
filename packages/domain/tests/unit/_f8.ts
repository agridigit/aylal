/** Helpers of the F8 unit tests: shared vectors (vectors/f8_*.json) and a module loader that fails by assertion (not by crash) while the rule is absent. */
import { readFileSync } from "node:fs";
import { expect } from "vitest";

export interface Vector {
  name: string;
  fn: string;
  input: unknown;
  expected: unknown;
  exact?: boolean;
}

export function load<T = Vector>(file: string): T[] {
  return JSON.parse(readFileSync(new URL(`../../vectors/${file}`, import.meta.url), "utf-8")) as T[];
}

type Fn = (...args: any[]) => any; // eslint-disable-line @typescript-eslint/no-explicit-any
export type Mod = Record<string, unknown>;

const camel = (s: string): string => s.replace(/_([a-z])/g, (_, c: string) => c.toUpperCase());

/** `fn("round_div")` accepts the snake_case vector name and resolves the camelCase export. */
export function pick(mod: Mod, name: string): Fn {
  const f = mod[camel(name)];
  expect(typeof f, `export ${camel(name)} is missing`).toBe("function");
  return f as Fn;
}

export function matches(actual: unknown, expected: unknown, exact = false, path = "$"): void {
  if (expected === null || typeof expected !== "object") {
    expect(actual, path).toEqual(expected);
  } else if (Array.isArray(expected)) {
    expect(Array.isArray(actual), path).toBe(true);
    expect((actual as unknown[]).length, path).toBe(expected.length);
    expected.forEach((e, i) => matches((actual as unknown[])[i], e, exact, `${path}[${i}]`));
  } else {
    expect(actual && typeof actual === "object", `${path} is not an object`).toBeTruthy();
    const a = actual as Record<string, unknown>;
    if (exact) expect(Object.keys(a).sort(), path).toEqual(Object.keys(expected).sort());
    for (const [k, e] of Object.entries(expected)) matches(a[k], e, exact, `${path}.${k}`);
  }
}

export function check(mod: Mod, v: Vector): void {
  matches(pick(mod, v.fn)(JSON.parse(JSON.stringify(v.input))), v.expected, v.exact ?? false);
}
