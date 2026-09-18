import type { Page } from "@playwright/test";

/** Заготовки ответов API. Все поля — как у настоящего бэкенда. */
export const USER = { id: "u1", email: "jury@locus.kz", name: "Жюри" };

export const CANDIDATES = [
  {
    id: "Q1798175",
    name: "Казахстанско-Британский технический университет",
    description: "университет в Алматы",
    aliases: ["КБТУ", "KBTU"],
    city: "Алматы",
    country: "Казахстан",
    coordinates: { lat: 43.236, lon: 76.929 },
    website: "https://kbtu.edu.kz/",
    commons_category: "Kazakh-British Technical University",
    inception: "2001-01-01",
    students: 4200,
    staff: 380,
    short_name: "КБТУ",
    wikidata_url: "https://www.wikidata.org/wiki/Q1798175",
    match_score: 1,
  },
  {
    id: "Q42",
    name: "KBTU Business School",
    description: "business school",
    aliases: [],
    city: null,
    country: null,
    coordinates: null,
    website: null,
    commons_category: null,
    wikidata_url: "https://www.wikidata.org/wiki/Q42",
    match_score: 0.8,
  },
];

function photo(id: string, title: string, category: string, extra: Record<string, unknown> = {}) {
  return {
    id,
    title,
    url: `https://upload.wikimedia.org/${id}.jpg`,
    thumb_url: null,
    source_page_url: `https://commons.wikimedia.org/wiki/File:${id}.jpg`,
    source_kinds: ["commons_category"],
    author: "Автор",
    license: "CC BY-SA 4.0",
    license_url: null,
    date: "2019-06-20",
    coordinates: null,
    width: 1200,
    height: 800,
    mime: "image/jpeg",
    description: null,
    commons_categories: [],
    category,
    category_source: "metadata",
    category_terms: [],
    // Снимок 2019 года: раньше на него вешалась пометка «может быть
    // устаревшим» — тест ниже следит, чтобы она не вернулась.
    stale: true,
    confidence: 0.81,
    evidence: {
      signals: [
        { key: "domain", label: "Домен", value: 0.9, weight: 0.25, detail: "commons.wikimedia.org" },
      ],
      geo_distance_m: null,
      domain_trust: 0.9,
      domain: "commons.wikimedia.org",
      source_count: 1,
      name_mentions: ["KBTU"],
      age_years: 6.2,
      classifier_confidence: 0.7,
      has_license: true,
      license_name: "CC BY-SA 4.0",
      notes: [],
    },
    phash: null,
    duplicate_of: null,
    reject_reason: null,
    reject_detail: null,
    ...extra,
  };
}

export const VERIFIED = [
  photo("main", "KBTU main building", "campus"),
  photo("grad", "KBTU graduation ceremony 2019", "student_life"),
  photo("canteen", "KBTU canteen", "food"),
];

const BASE_PROFILE = {
  university: CANDIDATES[0],
  verified: VERIFIED,
  needs_review: [],
  rejected: [],
  by_category: [],
  stats: { found: 9, unique: 7, duplicates: 2, verified: 3, needs_review: 0, rejected: 4, sources: 5 },
  description: null,
  warnings: [],
  took_ms: 2100,
  partial: false,
  surroundings: {
    radius_m: 1200,
    total: 2,
    available: true,
    error: null,
    groups: [
      {
        key: "transport",
        title: "Транспорт",
        count: 2,
        empty_reason: null,
        nearest: [
          { name: "Абая", distance_m: 78, walk_minutes: 1, osm_url: "https://www.openstreetmap.org/node/1", coordinates: null },
        ],
      },
      { key: "sports", title: "Спорт", count: 0, nearest: [], empty_reason: "в OSM в радиусе 1200 м ничего не отмечено" },
    ],
  },
  district: {
    radius_m: 1200,
    streets_total: 5,
    streets_lit: 2,
    streets_unlit: 1,
    streets_without_lit_tag: 2,
    lit_share_percent: 67,
    street_lamps: 2,
    crossings: 1,
    emergency_phones: 0,
    police: { name: "УВД", distance_m: 138, walk_minutes: 2, osm_url: "https://www.openstreetmap.org/node/9", coordinates: null },
    available: true,
    error: null,
  },
  logistics: {
    available: true,
    error: null,
    legs: [
      {
        key: "dorm_walk",
        title: "От общежития до кампуса пешком",
        from_name: "Общежитие №2",
        to_name: "КБТУ",
        distance_m: 237,
        minutes: 3,
        mode: "straight",
        note: "по прямой, пешком 4,5 км/ч — реальный путь длиннее",
      },
    ],
  },
  events: [
    { title: "Выпускной и вручение дипломов", photo_ids: ["grad"], count: 1, years: [2019] },
  ],
  videos: [],
  costs: {
    available: true,
    note: null,
    quotes: [
      {
        topic: "housing",
        topic_title: "Общежитие и проживание",
        quote: "Стоимость проживания в общежитии составляет 45 000 тенге в месяц.",
        page_title: "Общежитие",
        url: "https://kbtu.edu.kz/ru/dorm",
      },
    ],
  },
};

function sse(events: Array<Record<string, unknown>>): string {
  // Именно CRLF: так отдаёт sse-starlette, и разбор на фронте рассчитан на него.
  return events
    .map((e) => `event: ${e.stage}\r\ndata: ${JSON.stringify(e)}\r\n\r\n`)
    .join("");
}

export type MockOptions = {
  /** Профиль приходит двумя событиями: verified (фото) и done (с описанием). */
  splitProfile?: boolean;
  authFails?: boolean;
  /** Overpass промолчал: блок приходит пустым, но карта обязана остаться. */
  overpassDown?: boolean;
};

/** Подменяет все запросы к API. Бэкенд в браузерных тестах не участвует. */
export async function mockApi(page: Page, options: MockOptions = {}) {
  await page.route("**/api/auth/**", async (route) => {
    if (options.authFails) return route.abort("failed");
    await route.fulfill({ json: route.request().method() === "POST" ? { token: "t", user: USER } : USER });
  });

  await page.route("**/api/resolve**", (route) =>
    route.fulfill({ json: { query: "КБТУ", ambiguous: true, candidates: CANDIDATES, took_ms: 120 } }),
  );

  await page.route("**/api/profile**", (route) => {
    const profile = options.overpassDown
      ? {
          ...BASE_PROFILE,
          surroundings: {
            radius_m: 1200,
            groups: [],
            total: 0,
            available: false,
            error: "Overpass не ответил — список объектов рядом не собран",
          },
        }
      : BASE_PROFILE;
    const verifiedEvent = {
      stage: "verified",
      message: "Проверено: 3 (+0 требуют проверки)",
      elapsed_ms: 2100,
      counts: { verified: 3, needs_review: 0 },
      payload: { ...profile, partial: true, description: null },
    };
    const doneEvent = {
      stage: "done",
      message: "Готово за 2.4 с",
      elapsed_ms: 2400,
      counts: profile.stats,
      payload: profile,
    };
    const head = [
      { stage: "collecting", message: "Ищем вуз в Wikidata…", elapsed_ms: 0, counts: {}, payload: null },
      {
        stage: "resolved",
        message: "Вуз определён",
        elapsed_ms: 200,
        counts: {},
        payload: { needs_choice: false, university: CANDIDATES[0] },
      },
      { stage: "found", message: "Найдено файлов: 9", elapsed_ms: 900, counts: { found: 9 }, payload: null },
      { stage: "deduped", message: "Дубли удалены: −2", elapsed_ms: 1200, counts: { unique: 7, duplicates: 2 }, payload: null },
      { stage: "rejected", message: "Отклонено: дубли −2", elapsed_ms: 1500, counts: { rejected: 4 }, payload: null },
    ];
    const body = options.splitProfile
      ? sse([...head, verifiedEvent, doneEvent])
      : sse([...head, { ...verifiedEvent, payload: profile }, doneEvent]);

    return route.fulfill({
      status: 200,
      headers: { "content-type": "text/event-stream", "cache-control": "no-cache" },
      body,
    });
  });

  await page.route("**/api/wallet**", (route) => route.fulfill({ json: { coins: 0, uploads: 0 } }));
  await page.route("**/api/uploads**", (route) => route.fulfill({ json: { items: [] } }));
  // Картинки Commons наружу не тянем: в тестах сети нет.
  await page.route("**upload.wikimedia.org/**", (route) => route.abort());
}

/** Кладёт токен в localStorage — вход в тестах не через форму. */
export async function signIn(page: Page) {
  await page.addInitScript(() => {
    window.localStorage.setItem("campuslens-token", "test-token");
    // Заставка проверяется отдельно (e2e/intro.spec.ts) и здесь только мешала бы.
    window.localStorage.setItem("campuslens-intro-seen", "1");
  });
}
