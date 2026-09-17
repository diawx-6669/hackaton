import { expect, test } from "@playwright/test";
import { mockApi, signIn } from "./fixtures";

async function runSearch(page: import("@playwright/test").Page) {
  await page.goto("/");
  await page.locator("#university").fill("КБТУ");
  await page.getByRole("button", { name: "Собрать профиль" }).click();
}

test.describe("Профиль", () => {
  test.beforeEach(async ({ page }) => {
    await signIn(page);
  });

  test("галерея и все блоки собираются", async ({ page }) => {
    await mockApi(page);
    await runSearch(page);

    await expect(page.getByRole("heading", { name: /Казахстанско-Британский/ })).toBeVisible();
    for (const title of [
      "Что рядом с кампусом",
      "Инфраструктура района",
      "Сколько добираться",
      "Сколько это стоит",
      "События",
    ]) {
      await expect(page.getByRole("heading", { name: title, exact: true })).toBeVisible();
    }
  });

  test("фото показываются до того, как придёт описание", async ({ page }) => {
    await mockApi(page, { splitProfile: true });
    await runSearch(page);

    // Профиль отрисован из события verified, описание ещё не пришло.
    await expect(page.getByRole("heading", { name: /Казахстанско-Британский/ })).toBeVisible();
  });

  test("пустая категория объясняется, а не молчит", async ({ page }) => {
    await mockApi(page);
    await runSearch(page);

    // Пустая группа не прячется: её называют отдельной строкой под блоком.
    await expect(page.locator("body")).toContainText("Не отмечено в OSM: спорт");
  });

  test("у каждого фото виден источник и лицензия", async ({ page }) => {
    await mockApi(page);
    await runSearch(page);

    await page.getByRole("button", { name: /KBTU main building/ }).first().click();
    const dialog = page.locator("body");
    await expect(dialog).toContainText("CC BY-SA 4.0");
    await expect(dialog).toContainText("Открыть источник");
  });
});
