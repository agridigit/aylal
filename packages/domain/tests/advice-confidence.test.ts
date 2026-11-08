import { describe } from "vitest";
import * as mod from "../src/advice-confidence";
import { runVectors } from "./_f4";

describe("F4 confidence (shared vectors f4_confidence.json)", () => {
  runVectors(mod as Record<string, unknown>, "f4_confidence.json");
});
