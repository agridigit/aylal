import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: ".",
  testMatch: "*.spec.ts",
  snapshotPathTemplate: "{testDir}/__screenshots__/{arg}{ext}",
  workers: 1,
  expect: { toHaveScreenshot: { maxDiffPixelRatio: 0 } },
  use: {
    baseURL: process.env.STORYBOOK_URL ?? "http://localhost:6006",
    viewport: { width: 400, height: 400 },
    deviceScaleFactor: 1,
  },
});
