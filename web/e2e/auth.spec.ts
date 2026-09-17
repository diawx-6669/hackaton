import { expect, test } from "@playwright/test";
import { mockApi, signIn } from "./fixtures";

test.describe("Вход", () => {
  test("без входа поиска нет, есть приглашение войти", async ({ page }) => {
    await mockApi(page);
    await page.goto("/");

    await expect(page.getByRole("heading", { name: "Нужен вход" })).toBeVisible();
    await expect(page.locator("#university")).toHaveCount(0);
  });

  test("после входа появляется поле поиска", async ({ page }) => {
    await signIn(page);
    await mockApi(page);
    await page.goto("/");

    await expect(page.locator("#university")).toBeVisible();
  });

  test("недоступный бэкенд — это не «нужен вход»", async ({ page }) => {
    await signIn(page);
    await mockApi(page, { authFails: true });
    await page.goto("/");

    // Токен есть, сервер молчит: пользователю нельзя говорить, что он не вошёл.
    await expect(page.getByRole("heading", { name: "Сервер недоступен" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Повторить" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Нужен вход" })).toHaveCount(0);
  });
});
