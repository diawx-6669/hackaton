import { expect, test } from "@playwright/test";
import { mockApi, signIn } from "./fixtures";

test.describe("Поиск", () => {
  test.beforeEach(async ({ page }) => {
    await signIn(page);
    await mockApi(page);
  });

  test("подсказки появляются при наборе и подставляются по клику", async ({ page }) => {
    await page.goto("/");
    await page.locator("#university").fill("КБТУ");

    const hints = page.locator("#university-hints li");
    await expect(hints.first()).toBeVisible();
    await expect(hints).toHaveCount(2);
    await expect(hints.first()).toContainText("Казахстанско-Британский");
    await expect(hints.first()).toContainText("Алматы");

    await hints.first().click();
    await expect(page.locator("#university-hints")).toHaveCount(0);
  });

  test("подсказками можно управлять с клавиатуры", async ({ page }) => {
    await page.goto("/");
    const input = page.locator("#university");
    await input.fill("КБТУ");
    await expect(page.locator("#university-hints li").first()).toBeVisible();

    await input.press("ArrowDown");
    await expect(page.locator('#university-hints li[aria-selected="true"]')).toHaveCount(1);

    await input.press("Escape");
    await expect(page.locator("#university-hints")).toHaveCount(0);
  });
});
