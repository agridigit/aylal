import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { flattenKeys } from "../src/index";

const KEYS = ["legend.title", "legend.ok", "legend.watch", "legend.act", "legend.unknown", "offline.banner", "empty", "error", "loading", "open_field"];
const load = (l: string) => flattenKeys(JSON.parse(readFileSync(join(__dirname, "..", "locales", l, "map.json"), "utf8")));

describe("map.json keys (T054)", () => {
  for (const l of ["ary", "ar", "fr"])
    it(`Given ${l}/map.json, When reading the map keys, Then each is a non-empty string`, () => {
      const flat = load(l);
      expect(KEYS.filter((k) => !(flat[k] ?? "").trim()), l).toEqual([]);
    });
});
