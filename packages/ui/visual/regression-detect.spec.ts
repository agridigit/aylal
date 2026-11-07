import { expect, test } from "@playwright/test";

test("Given an unintended change to a component, When captures are compared, Then the regression is detected", async ({ page }) => {
  await page.goto("/iframe.html?id=button--primary-default&viewMode=story&globals=theme:light;direction:ltr");
  await page.waitForSelector("#storybook-root *");
  await expect(page).toHaveScreenshot("Button-light-ltr.png");
  await page.addStyleTag({ content: "#storybook-root * { background-color: #ff00ff !important; border-radius: 0 !important; }" });
  await expect(expect(page).toHaveScreenshot("Button-light-ltr.png")).rejects.toThrow();
});
