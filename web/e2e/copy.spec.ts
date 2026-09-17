import { expect, test } from "@playwright/test";
import { mockApi, signIn } from "./fixtures";

/**
 * Тексты, о которых легко забыть при следующей правке.
 * Каждый пункт здесь — то, что мы уже один раз чинили руками.
 */
test.describe("Тексты интерфейса", () => {
  test.beforeEach(async ({ page }) => {
    await signIn(page);
    await mockApi(page);
    await page.goto("/");
    await page.locator("#university").fill("КБТУ");
    await page.getByRole("button", { name: "Собрать профиль" }).click();
    await expect(page.getByRole("heading", { name: /Казахстанско-Британский/ })).toBeVisible();
  });

  test("пометки «может быть устаревшим» больше нет", async ({ page }) => {
    // В фикстуре у всех фото stale: true — раньше это рисовало бейдж.
    await expect(page.locator("body")).not.toContainText("устаревш");
  });

  test("в интерфейсе нет эмодзи", async ({ page }) => {
    const text = await page.locator("body").innerText();
    const emoji = text.match(
      /[\u{1F300}-\u{1FAFF}\u{2705}\u{274C}\u{26A0}\u{1F4CD}\u{1F517}\u{1F5BC}\u{FE0F}]/gu,
    );
    expect(emoji, `нашлись эмодзи: ${emoji?.join(" ")}`).toBeNull();
  });

  test("сводной оценки безопасности не появилось", async ({ page }) => {
    const text = await page.locator("body").innerText();
    // Балл по этим данным честно не считается — см. services/osm.py.
    expect(text).not.toMatch(/safe[- ]?score|индекс безопасности|оценка безопасности:/i);
    await expect(page.locator("body")).toContainText("Сводной оценки безопасности мы не выводим");
  });

  test("оценка по прямой подписана как оценка", async ({ page }) => {
    await expect(page.locator("body")).toContainText("оценка по прямой");
  });

  test("цена подана цитатой со ссылкой на источник", async ({ page }) => {
    await expect(page.locator("body")).toContainText("45 000 тенге");
    await expect(page.getByRole("link", { name: /kbtu\.edu\.kz\/ru\/dorm/ })).toBeVisible();
  });
});
