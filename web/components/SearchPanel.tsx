"use client";

import { useState } from "react";
import { Search } from "./Icons";
import { SubscribeForm } from "./SubscribeForm";

type Props = {
  onSearch: (query: string) => void;
  busy: boolean;
  onCancel: () => void;
  /** Компактный вид: только поле и кнопка, без вкладок — когда профиль уже собирается. */
  compact?: boolean;
};

// Примеры специально разного калибра: крупные, региональные и зарубежные —
// чтобы было видно, что сервис не ограничен списком известных вузов.
const EXAMPLES = [
  "КБТУ",
  "Nazarbayev University",
  "КазНУ",
  "Актюбинский региональный университет",
  "Toraighyrov University",
  "МГУ",
];

// Только проверяемые факты: никаких «89% достоверности» и прочих
// придуманных метрик — по ТЗ подделывать показатели нельзя.
const FACTS = [
  { value: "8", label: "категорий кампуса" },
  { value: "25 с", label: "бюджет на сборку" },
  { value: "2", label: "источника Wikimedia" },
  { value: "0", label: "захардкоженных фото" },
];

export function SearchPanel({ onSearch, busy, onCancel, compact = false }: Props) {
  const [tab, setTab] = useState<"search" | "about" | "notfound">("search");
  const [value, setValue] = useState("");

  const form = (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        const q = value.trim();
        if (q.length >= 2) onSearch(q);
      }}
      className={compact ? "flex flex-col gap-2 sm:flex-row sm:items-center" : ""}
    >
      {!compact && (
        <>
          <h2 className="font-display text-2xl font-semibold">Найдите свой университет</h2>
          <p className="mt-1 text-xs text-[var(--muted)]">
            Введите название — остальное соберём сами.
          </p>
          <label className="mt-6 block text-xs font-medium" htmlFor="university">
            Университет
          </label>
        </>
      )}

      <div className={`field flex items-center rounded-lg px-3 ${compact ? "flex-1" : "mt-2"}`}>
        <Search className="mr-2 h-4 w-4 shrink-0 text-[var(--muted)]" />
        <input
          id={compact ? "university-compact" : "university"}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="Например, КБТУ"
          aria-label="Название университета"
          autoComplete="off"
          className="h-11 min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-[var(--muted)]"
        />
      </div>

      {!compact && (
        <div className="mt-3 flex flex-wrap gap-2">
          {EXAMPLES.map((e) => (
            <button
              key={e}
              type="button"
              disabled={busy}
              onClick={() => {
                setValue(e);
                onSearch(e);
              }}
              className="rounded-md border border-[var(--border)] px-2 py-1 text-xs text-[var(--muted)] transition hover:border-[var(--accent)] hover:text-[var(--foreground)] disabled:opacity-40"
            >
              {e}
            </button>
          ))}
        </div>
      )}

      {busy ? (
        <button
          type="button"
          onClick={onCancel}
          className={`h-11 rounded-lg border border-[var(--border)] px-5 font-medium text-[var(--muted)] transition hover:text-[var(--foreground)] ${
            compact ? "shrink-0" : "mt-6 w-full"
          }`}
        >
          Отменить
        </button>
      ) : (
        <button
          type="submit"
          disabled={value.trim().length < 2}
          className={`primary-action h-11 rounded-lg font-semibold ${
            compact ? "shrink-0 px-6" : "mt-6 w-full"
          }`}
        >
          Собрать профиль
        </button>
      )}

      {!compact && (
        <p className="mt-6 text-center text-[11px] text-[var(--muted)]">
          Открытые данные · проверяемые источники
        </p>
      )}
    </form>
  );

  if (compact) {
    return <div className="glass-panel rounded-2xl p-3">{form}</div>;
  }

  return (
    <section className="glass-panel w-full rounded-2xl p-5 sm:p-7" aria-label="Поиск университета">
      <div className="tab-shell grid grid-cols-3 rounded-full p-1">
        <button
          type="button"
          onClick={() => setTab("search")}
          className={`tab-button rounded-full ${tab === "search" ? "tab-active" : ""}`}
        >
          Поиск
        </button>
        <button
          type="button"
          onClick={() => setTab("about")}
          className={`tab-button rounded-full ${tab === "about" ? "tab-active" : ""}`}
        >
          О проекте
        </button>
        <button
          type="button"
          onClick={() => setTab("notfound")}
          className={`tab-button rounded-full ${tab === "notfound" ? "tab-active" : ""}`}
        >
          Нет вуза?
        </button>
      </div>

      {tab === "search" ? (
        <div className="mt-6">{form}</div>
      ) : tab === "notfound" ? (
        <div className="mt-6 min-h-[308px]">
          <SubscribeForm />
        </div>
      ) : (
        <div className="mt-6 min-h-[308px]">
          <h2 className="font-display text-2xl font-semibold">CampusLens</h2>
          <p className="mt-3 text-sm leading-6 text-[var(--muted)]">
            Сервис собирает фотографии кампуса из Wikidata и Wikimedia Commons, убирает дубли
            и показывает, почему каждому снимку можно доверять: расстояние геотега до кампуса,
            доверие к домену, привязка к вузу, свежесть. Если подтвердить не удалось — так
            и пишем, а не додумываем.
          </p>
          <div className="mt-6 grid grid-cols-2 gap-3">
            {FACTS.map((f) => (
              <span
                key={f.label}
                className="rounded-lg border border-[var(--border)] bg-[oklch(0.28_0.035_265_/_40%)] p-3 text-xs text-[var(--muted)]"
              >
                <b className="block font-mono text-lg text-[var(--foreground)]">{f.value}</b>
                {f.label}
              </span>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
