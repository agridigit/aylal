import { expect, test } from "@playwright/test";
import { catalog, STATES } from "../src/components/catalog";

const THEMES = ["light", "dark", "sun"] as const;
const DIRS = ["ltr", "rtl"] as const;
const slug = (s: string) => s.replace(/([a-z])([A-Z])/g, "$1-$2").toLowerCase();
const pascal = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

for (const c of catalog) for (const theme of THEMES) for (const dir of DIRS) {
  test(`Given ${c.name} in ${theme}/${dir}, When captured, Then it matches the reference`, async ({ page }) => {
    const story = `${pascal(c.variants[0])}${pascal(STATES[0])}`;
    await page.goto(`/iframe.html?id=${slug(c.name)}--${slug(story)}&viewMode=story&globals=theme:${theme};direction:${dir}`);
    await page.waitForSelector("#storybook-root *");
    await expect(page).toHaveScreenshot(`${c.name}-${theme}-${dir}.png`);
  });
}
