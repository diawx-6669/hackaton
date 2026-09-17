import { expect, test } from "@playwright/test";
import { mockApi, signIn } from "./fixtures";

/** Мобильная версия обязательна по ТЗ, поэтому проверяем её отдельно. */
test.describe("Мобильная версия", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test("нет горизонтальной прокрутки на главной и в профиле", async ({ page }) => {
    await signIn(page);
    await mockApi(page);
    await page.goto("/");

    const overflowOnHome = await page.evaluate(
      () => document.documentElement.scrollWidth > window.innerWidth + 1,
    );
    expect(overflowOnHome, "горизонтальная прокрутка на главной").toBe(false);

    await page.locator("#university").fill("КБТУ");
    await page.getByRole("button", { name: "Собрать профиль" }).click();
    await expect(page.getByRole("heading", { name: /Казахстанско-Британский/ })).toBeVisible();

    const overflowOnProfile = await page.evaluate(
      () => document.documentElement.scrollWidth > window.innerWidth + 1,
    );
    expect(overflowOnProfile, "горизонтальная прокрутка в профиле").toBe(false);
  });
});
