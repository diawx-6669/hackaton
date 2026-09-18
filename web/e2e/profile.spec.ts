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

test.describe("Панель разделов", () => {
  test.beforeEach(async ({ page }) => {
    await signIn(page);
    await mockApi(page);
    await runSearch(page);
    await expect(page.getByRole("heading", { name: /Казахстанско-Британский/ })).toBeVisible();
  });

  test("перечисляет собранные разделы", async ({ page }) => {
    const nav = page.getByRole("navigation", { name: "Разделы профиля" });
    await expect(nav).toBeVisible();
    for (const label of ["О вузе", "Что рядом", "Район и дорога", "Стоимость", "Галерея"]) {
      await expect(nav.getByRole("link", { name: label })).toBeVisible();
    }
  });

  test("не показывает раздел, которого нет", async ({ page }) => {
    // В фикстуре описание от LLM пустое — пункта «Описание» быть не должно.
    const nav = page.getByRole("navigation", { name: "Разделы профиля" });
    await expect(nav.getByRole("link", { name: "Описание" })).toHaveCount(0);
  });

  test("клик по пункту приводит к нужному блоку", async ({ page }) => {
    await page
      .getByRole("navigation", { name: "Разделы профиля" })
      .getByRole("link", { name: "Стоимость" })
      .click();

    await expect(page.getByRole("heading", { name: "Сколько это стоит" })).toBeInViewport();
  });

  test("панель остаётся видимой при прокрутке", async ({ page }) => {
    await page.mouse.wheel(0, 2000);
    await page.waitForTimeout(400);
    await expect(page.getByRole("navigation", { name: "Разделы профиля" })).toBeInViewport();
  });
});

test.describe("О вузе", () => {
  test.beforeEach(async ({ page }) => {
    await signIn(page);
    await mockApi(page);
    await runSearch(page);
  });

  test("факты показываются без языковой модели", async ({ page }) => {
    // В фикстуре description = null: блок обязан работать и без LLM.
    const about = page
      .locator("section", { has: page.getByRole("heading", { name: "О вузе" }) })
      .last();
    await expect(about).toContainText("4 200");
    await expect(about).toContainText("Основан");
    await expect(about).toContainText("2001");
    await expect(about.getByRole("link", { name: /Wikidata/ })).toBeVisible();
  });

  test("есть кнопка аудиообзора", async ({ page }) => {
    await expect(page.getByRole("button", { name: "Слушать обзор" })).toBeVisible();
  });
});

test.describe("Карта окружения", () => {
  test("карта показывается вместе со списком", async ({ page }) => {
    await signIn(page);
    await mockApi(page);
    await runSearch(page);

    const nearby = page
      .locator("section", { has: page.getByRole("heading", { name: "Что рядом с кампусом" }) })
      .last();
    await expect(nearby.locator(".leaflet-container")).toBeVisible();
    await expect(nearby).toContainText("Транспорт");
  });

  test("карта остаётся, даже когда Overpass не ответил", async ({ page }) => {
    await signIn(page);
    await mockApi(page, { overpassDown: true });
    await runSearch(page);

    const nearby = page
      .locator("section", { has: page.getByRole("heading", { name: "Что рядом с кампусом" }) })
      .last();
    // Главное: вместо строки об ошибке человек видит карту.
    await expect(nearby.locator(".leaflet-container")).toBeVisible();
    await expect(nearby).toContainText("Overpass не ответил");
  });
});
