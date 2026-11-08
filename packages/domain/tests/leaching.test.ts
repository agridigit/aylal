import { describe } from "vitest";
import * as mod from "../src/leaching";
import { runVectors } from "./_f4";

describe("F4 leaching (shared vectors f4_leaching.json)", () => {
  runVectors(mod as Record<string, unknown>, "f4_leaching.json");
});
