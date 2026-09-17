import { defineConfig, devices } from "@playwright/test";

/**
 * Браузерные тесты CampusLens.
 *
 * Бэкенд в них не участвует: каждый тест подменяет ответы API через
 * page.route(). Так тесты не зависят ни от сети, ни от лимитов Wikimedia и
 * проверяют ровно то, за что отвечает фронтенд — что показано пользователю.
 *
 * Про executablePath: в образе уже лежит Chromium, и «playwright install»
 * запускать не нужно. Путь берётся из PLAYWRIGHT_CHROMIUM_PATH, если он задан,
 * иначе используется браузер, который скачал сам Playwright.
 */
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_PATH || undefined;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 2 : undefined,
  reporter: process.env.CI ? "github" : "list",
  timeout: 30_000,
  use: {
    baseURL: "http://127.0.0.1:3100",
    trace: "on-first-retry",
    launchOptions: executablePath ? { executablePath } : {},
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile", use: { ...devices["Pixel 7"] } },
  ],
  webServer: {
    // Прод-сборка, а не dev: тесты должны проверять то, что уедет на Vercel.
    command: "npm run build && npx next start -p 3100",
    url: "http://127.0.0.1:3100",
    reuseExistingServer: !process.env.CI,
    timeout: 180_000,
    env: {
      // Адрес несуществующий: все запросы к API перехватываются в тестах.
      NEXT_PUBLIC_API_BASE_URL: "http://127.0.0.1:9",
    },
  },
});
