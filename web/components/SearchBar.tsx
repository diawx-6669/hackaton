"use client";

import { useState } from "react";
import { Search } from "./Icons";

type Props = {
  onSearch: (query: string) => void;
  busy: boolean;
  onCancel: () => void;
};

const EXAMPLES = ["КБТУ", "Nazarbayev University", "КазНУ", "МГУ"];

export function SearchBar({ onSearch, busy, onCancel }: Props) {
  const [value, setValue] = useState("");

  return (
    <div className="w-full">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          const q = value.trim();
          if (q.length >= 2) onSearch(q);
        }}
        // Поле и кнопка — один визуальный блок с общей рамкой и подсветкой фокуса.
        className="flex flex-col gap-2 rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-2 focus-within:border-[var(--accent)] sm:flex-row sm:items-center"
      >
        <span className="pointer-events-none hidden pl-2 text-[var(--muted)] sm:block">
          <Search />
        </span>
        <input
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="Название университета, например «КБТУ»"
          aria-label="Название университета"
          className="w-full bg-transparent px-3 py-2.5 text-base outline-none placeholder:text-[var(--muted)]"
        />
        {busy ? (
          <button
            type="button"
            onClick={onCancel}
            className="shrink-0 whitespace-nowrap rounded-xl border border-[var(--border)] bg-[var(--surface-2)] px-5 py-2.5 font-medium text-[var(--muted)] transition hover:text-[var(--foreground)]"
          >
            Отменить
          </button>
        ) : (
          <button
            type="submit"
            disabled={value.trim().length < 2}
            className="shrink-0 whitespace-nowrap rounded-xl bg-[var(--accent)] px-5 py-2.5 font-semibold text-[#06121d] transition hover:brightness-110 disabled:opacity-40 disabled:hover:brightness-100"
          >
            Собрать профиль
          </button>
        )}
      </form>

      <div className="mt-3 flex flex-wrap items-center gap-2 text-sm text-[var(--muted)]">
        <span>Примеры:</span>
        {EXAMPLES.map((e) => (
          <button
            key={e}
            type="button"
            disabled={busy}
            onClick={() => {
              setValue(e);
              onSearch(e);
            }}
            className="rounded-lg border border-[var(--border)] px-2.5 py-1 transition hover:border-[var(--accent)] hover:text-[var(--foreground)] disabled:opacity-40"
          >
            {e}
          </button>
        ))}
      </div>
    </div>
  );
}
