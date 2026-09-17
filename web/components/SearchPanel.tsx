"use client";

import { useEffect, useRef, useState } from "react";
import { Search, Pin } from "./Icons";
import { SubscribeForm } from "./SubscribeForm";
import { resolveUniversity } from "@/lib/api";
import type { University } from "@/lib/types";

type Props = {
  onSearch: (query: string) => void;
  /** Выбор из подсказок: сразу отдаём QID, минуя повторный resolve. */
  onPick?: (university: University) => void;
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

export function SearchPanel({ onSearch, onPick, busy, onCancel, compact = false }: Props) {
  const [tab, setTab] = useState<"search" | "about" | "notfound">("search");
  const [value, setValue] = useState("");
  const [hints, setHints] = useState<University[]>([]);
  const [active, setActive] = useState(-1);
  const [open, setOpen] = useState(false);
  // Запрос, для которого подсказки уже показаны: чтобы не дёргать Wikidata
  // повторно после выбора из списка или отправки формы.
  const settled = useRef("");

  // Подсказки: тот же /api/resolve, но с задержкой и отменой предыдущего
  // запроса — на каждую букву в Wikidata не ходим.
  useEffect(() => {
    const q = value.trim();
    if (q.length < 2 || q === settled.current) {
      setHints([]);
      return;
    }
    const controller = new AbortController();
    const timer = setTimeout(() => {
      void (async () => {
        try {
          const res = await resolveUniversity(q, controller.signal);
          if (controller.signal.aborted) return;
          setHints(res.candidates.slice(0, 6));
          setActive(-1);
          setOpen(true);
        } catch {
          // Подсказки не обязательны: молча выключаем, поиск по Enter продолжает работать.
          if (!controller.signal.aborted) setHints([]);
        }
      })();
    }, 250);

    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [value]);

  const pick = (u: University) => {
    settled.current = u.name;
    setValue(u.name);
    setOpen(false);
    setHints([]);
    if (onPick) onPick(u);
    else onSearch(u.name);
  };

  const submit = (q: string) => {
    settled.current = q;
    setOpen(false);
    onSearch(q);
  };

  const form = (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        const q = value.trim();
        if (active >= 0 && hints[active]) {
          pick(hints[active]);
          return;
        }
        if (q.length >= 2) submit(q);
      }}
      className={compact ? "flex flex-col gap-2 sm:flex-row sm:items-center" : ""}
    >
      {!compact && (
        <>
          <h2 className="font-display text-2xl font-semibold">Найдите свой университет</h2>

          <label className="mt-6 block text-xs font-medium" htmlFor="university">
            Университет
          </label>
        </>
      )}

      <div className={`relative ${compact ? "flex-1" : "mt-2"}`}>
        <div className="field flex items-center rounded-lg px-3">
          <Search className="mr-2 h-4 w-4 shrink-0 text-[var(--muted)]" />
          <input
            id={compact ? "university-compact" : "university"}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onFocus={() => hints.length > 0 && setOpen(true)}
            onBlur={() => setTimeout(() => setOpen(false), 120)}
            onKeyDown={(e) => {
              if (!open || hints.length === 0) return;
              if (e.key === "ArrowDown") {
                e.preventDefault();
                setActive((i) => (i + 1) % hints.length);
              } else if (e.key === "ArrowUp") {
                e.preventDefault();
                setActive((i) => (i <= 0 ? hints.length - 1 : i - 1));
              } else if (e.key === "Escape") {
                setOpen(false);
              }
            }}
            placeholder="Например, КБТУ"
            aria-label="Название университета"
            role="combobox"
            aria-expanded={open && hints.length > 0}
            aria-controls="university-hints"
            autoComplete="off"
            className="h-11 min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-[var(--muted)]"
          />
        </div>

        {open && hints.length > 0 && (
          <ul
            id="university-hints"
            role="listbox"
            className="absolute left-0 right-0 top-[calc(100%+6px)] z-30 max-h-72 overflow-y-auto rounded-xl border border-[var(--border)] bg-[var(--surface)] shadow-xl backdrop-blur"
          >
            {hints.map((h, i) => (
              <li key={h.id} role="option" aria-selected={i === active}>
                <button
                  type="button"
                  // onMouseDown, а не onClick: blur поля успевает закрыть список раньше клика.
                  onMouseDown={(e) => {
                    e.preventDefault();
                    pick(h);
                  }}
                  onMouseEnter={() => setActive(i)}
                  className={`flex w-full flex-col gap-0.5 px-3 py-2 text-left ${
                    i === active ? "bg-[var(--surface-2)]" : ""
                  }`}
                >
                  <span className="flex items-baseline justify-between gap-2">
                    <span className="truncate text-sm">{h.name}</span>
                    <span className="shrink-0 font-mono text-[11px] text-[var(--muted)]">
                      {Math.round(h.match_score * 100)}%
                    </span>
                  </span>
                  <span className="flex items-center gap-1 truncate text-[11px] text-[var(--muted)]">
                    {(h.city || h.country) && <Pin className="h-3 w-3 shrink-0 opacity-70" />}
                    {[h.city, h.country].filter(Boolean).join(", ") || h.description || h.id}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
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
                submit(e);
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
            Собираем фото кампуса из Wikidata и Wikimedia Commons, убираем дубли и показываем,
            почему снимку можно доверять: геотег, домен, привязка к вузу, свежесть.
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
