import { describe } from "vitest";
import * as mod from "../src/effective-rain";
import { runVectors } from "./_f4";

describe("F4 effective rain (shared vectors f4_effective_rain.json)", () => {
  runVectors(mod as Record<string, unknown>, "f4_effective_rain.json");
});
