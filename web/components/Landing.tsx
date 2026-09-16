import { CATEGORY_LABELS, type PhotoCategory } from "@/lib/types";
import {
  Clock,
  EyeOpen,
  Filter,
  Gauge,
  Layers,
  Link as LinkIcon,
  Pin,
  Scales,
  Search,
  ShieldCheck,
} from "./Icons";

const PILLARS = [
  {
    icon: ShieldCheck,
    title: "Только подтверждённое",
    text: "15 проверенных фото лучше 100 случайных. У каждого снимка — источник, автор и лицензия.",
  },
  {
    icon: Scales,
    title: "Видно, почему поверили",
    text: "Балл достоверности разложен на улики: геотег, домен, привязка к вузу, свежесть.",
  },
  {
    icon: EyeOpen,
    title: "Честно про пустоту",
    text: "Если подтверждённых фото по категории нет — так и написано. Ничего не додумываем.",
  },
];

const STEPS = [
  {
    icon: Search,
    title: "Находим вуз",
    text: "Wikidata по названию, аббревиатуре или опечатке. Забираем координаты, сайт и категорию Commons.",
  },
  {
    icon: Layers,
    title: "Собираем параллельно",
    text: "Категория вуза в Wikimedia Commons и геопоиск файлов в радиусе километра от кампуса — одновременно.",
  },
  {
    icon: Filter,
    title: "Чистим",
    text: "Убираем дубли, стоковые домены, логотипы и схемы, снимки чужих зданий. Каждый отказ — с причиной.",
  },
  {
    icon: Gauge,
    title: "Оцениваем и раскладываем",
    text: "Считаем Confidence Score по уликам и разносим фото по восьми категориям кампуса.",
  },
];

// Веса — ровно те, что зашиты в api/app/services/evidence.py.
const SIGNALS = [
  { label: "Геотег", weight: 0.3, hint: "расстояние от снимка до координат кампуса" },
  { label: "Источник", weight: 0.25, hint: "сайт вуза → Commons → .edu → неизвестный; стоки отклоняем" },
  { label: "Привязка к вузу", weight: 0.25, hint: "файл лежит в категории Commons самого вуза" },
  { label: "Классификатор", weight: 0.2, hint: "уверенность в определённой категории" },
  { label: "Вуз в метаданных", weight: 0.15, hint: "название в имени файла, подписи или категориях" },
  { label: "Повтор в источниках", weight: 0.1, hint: "одно фото пришло из нескольких сборщиков" },
  { label: "Свежесть", weight: 0.05, hint: "снимок старше пяти лет помечаем как устаревший" },
];

const CATEGORIES: PhotoCategory[] = [
  "campus",
  "dorms",
  "classrooms",
  "libraries",
  "labs",
  "sports",
  "student_life",
  "city",
];

export function Pillars() {
  return (
    <section className="grid gap-3 sm:grid-cols-3">
      {PILLARS.map(({ icon: Icon, title, text }) => (
        <article key={title} className="card card-hover p-4 sm:p-5">
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-[var(--surface-2)] text-[var(--accent)]">
            <Icon />
          </span>
          <h3 className="mt-3 font-semibold">{title}</h3>
          <p className="mt-1.5 text-sm leading-relaxed text-[var(--muted)]">{text}</p>
        </article>
      ))}
    </section>
  );
}

export function HowItWorks() {
  return (
    <section className="grid gap-4">
      <header className="flex flex-wrap items-end justify-between gap-2">
        <h2 className="text-xl font-semibold sm:text-2xl">Как это работает</h2>
        <p className="flex items-center gap-1.5 text-sm text-[var(--muted)]">
          <Clock className="h-4 w-4" />
          общий бюджет — <span className="font-mono text-[var(--foreground)]">25 секунд</span>
        </p>
      </header>

      <ol className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {STEPS.map(({ icon: Icon, title, text }, i) => (
          <li key={title} className="card card-hover relative p-4">
            <span className="absolute right-3 top-3 font-mono text-xs text-[var(--muted)]">
              0{i + 1}
            </span>
            <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-[var(--surface-2)] text-[var(--accent)]">
              <Icon />
            </span>
            <h3 className="mt-3 font-semibold">{title}</h3>
            <p className="mt-1.5 text-sm leading-relaxed text-[var(--muted)]">{text}</p>
          </li>
        ))}
      </ol>
    </section>
  );
}

export function TrustFormula() {
  const max = Math.max(...SIGNALS.map((s) => s.weight));

  return (
    <section className="card grid gap-4 p-4 sm:p-6">
      <header>
        <h2 className="text-xl font-semibold sm:text-2xl">Из чего складывается доверие</h2>
        <p className="mt-1 max-w-2xl text-sm leading-relaxed text-[var(--muted)]">
          Это не «магия ИИ», а взвешенная сумма улик — каждая видна в карточке фото.
          Если сигнала нет, веса пере-нормируются: среднее значение вместо него не подставляется.
        </p>
      </header>

      <ul className="grid gap-2.5">
        {SIGNALS.map((s) => (
          <li key={s.label} className="grid gap-1 sm:grid-cols-[13rem_minmax(0,1fr)] sm:items-baseline sm:gap-4">
            <div className="flex items-baseline justify-between gap-2">
              <span className="whitespace-nowrap text-sm font-medium">{s.label}</span>
              <span className="font-mono text-xs text-[var(--accent)]">{s.weight.toFixed(2)}</span>
            </div>
            <div>
              <div className="h-1.5 w-full overflow-hidden rounded-full bg-[var(--surface-2)]">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-[var(--accent-deep)] to-[var(--accent)]"
                  style={{ width: `${(s.weight / max) * 100}%` }}
                />
              </div>
              <p className="mt-1 text-xs text-[var(--muted)]">{s.hint}</p>
            </div>
          </li>
        ))}
      </ul>

      <footer className="flex flex-wrap gap-2 border-t border-[var(--border-soft)] pt-3 text-xs">
        <span className="rounded-lg bg-[var(--ok)]/12 px-2 py-1 text-[var(--ok)]">
          ✅ Проверено — балл 62 и выше
        </span>
        <span className="rounded-lg bg-[var(--warn)]/12 px-2 py-1 text-[var(--warn)]">
          ⚠️ Требует проверки — 38…62
        </span>
        <span className="rounded-lg bg-[var(--bad)]/12 px-2 py-1 text-[var(--bad)]">
          ❌ Отклонено — с указанием причины
        </span>
      </footer>
    </section>
  );
}

export function CategoriesStrip() {
  return (
    <section className="grid gap-3">
      <h2 className="text-xl font-semibold sm:text-2xl">Восемь срезов кампуса</h2>
      <ul className="flex flex-wrap gap-2">
        {CATEGORIES.map((c) => (
          <li
            key={c}
            className="rounded-xl border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-sm"
          >
            {CATEGORY_LABELS[c]}
          </li>
        ))}
      </ul>
      <p className="text-sm text-[var(--muted)]">
        Плюс отдельный класс «мусор» — логотипы, гербы, схемы, дипломы и портреты в галерею не попадают.
      </p>
    </section>
  );
}

export function SourcesNote() {
  return (
    <section className="card grid gap-3 p-4 sm:grid-cols-[auto_minmax(0,1fr)] sm:items-center sm:gap-5 sm:p-5">
      <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[var(--surface-2)] text-[var(--accent)]">
        <LinkIcon className="h-6 w-6" />
      </span>
      <div>
        <h2 className="font-semibold">Ничего не выдумано</h2>
        <p className="mt-1 text-sm leading-relaxed text-[var(--muted)]">
          В проекте нет ни одной захардкоженной фотографии. Всё ищется на лету в{" "}
          <a
            href="https://www.wikidata.org"
            target="_blank"
            rel="noopener noreferrer"
            className="text-[var(--accent)] underline"
          >
            Wikidata
          </a>{" "}
          и{" "}
          <a
            href="https://commons.wikimedia.org"
            target="_blank"
            rel="noopener noreferrer"
            className="text-[var(--accent)] underline"
          >
            Wikimedia Commons
          </a>
          . У каждого снимка своя лицензия — она указана в карточке вместе с автором и ссылкой
          на страницу-источник.
        </p>
      </div>
    </section>
  );
}

export function HeroStats() {
  return (
    <ul className="flex flex-wrap items-center gap-x-5 gap-y-2 text-sm text-[var(--muted)]">
      <li className="flex items-center gap-1.5">
        <Pin className="h-4 w-4 text-[var(--accent)]" />8 категорий кампуса
      </li>
      <li className="flex items-center gap-1.5">
        <LinkIcon className="h-4 w-4 text-[var(--accent)]" />
        источник и лицензия у каждого фото
      </li>
      <li className="flex items-center gap-1.5">
        <Clock className="h-4 w-4 text-[var(--accent)]" />
        до 30 секунд
      </li>
    </ul>
  );
}
