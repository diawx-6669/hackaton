import { expect, test } from "@playwright/test";
import { mockApi } from "./fixtures";

/**
 * Интро проверяем поведением, а не картинкой: Chromium в этом окружении
 * собран без H.264, поэтому сам ролик здесь не проигрывается. Важно другое —
 * что заставка не запирает пользователя и не возвращается на каждый заход.
 */
test.describe("Интро", () => {
  test.beforeEach(async ({ page }) => {
    await mockApi(page);
  });

  test("показывается при первом заходе и закрывается кнопкой", async ({ page }) => {
    await page.goto("/");
    const intro = page.getByRole("dialog", { name: "Заставка CampusLens" });
    await expect(intro).toBeVisible();

    await page.getByRole("button", { name: "Пропустить" }).click();
    await expect(intro).toHaveCount(0);
  });

  test("после просмотра не возвращается", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: "Пропустить" }).click();
    await expect(page.getByRole("dialog", { name: "Заставка CampusLens" })).toHaveCount(0);

    await page.reload();
    await expect(page.getByRole("dialog", { name: "Заставка CampusLens" })).toHaveCount(0);
  });

  test("закрывается по Esc", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("dialog", { name: "Заставка CampusLens" })).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog", { name: "Заставка CampusLens" })).toHaveCount(0);
  });

  test("не показывается тем, кто просил меньше анимации", async ({ browser }) => {
    const ctx = await browser.newContext({ reducedMotion: "reduce" });
    const page = await ctx.newPage();
    await mockApi(page);
    await page.goto("/");

    await expect(page.getByRole("dialog", { name: "Заставка CampusLens" })).toHaveCount(0);
    await ctx.close();
  });

  test("логотип стоит в шапке", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: "Пропустить" }).click();
    const logo = page.locator('header img[src*="logo"]');
    await expect(logo).toBeVisible();
  });
});

test("заставку можно пересмотреть кнопкой в шапке", async ({ page }) => {
  await mockApi(page);
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto("/");
  await page.getByRole("button", { name: "Пропустить" }).click();
  await expect(page.getByRole("dialog", { name: "Заставка CampusLens" })).toHaveCount(0);

  await page.locator("header").getByRole("button", { name: "Заставка" }).click();
  await expect(page.getByRole("dialog", { name: "Заставка CampusLens" })).toBeVisible();
});
