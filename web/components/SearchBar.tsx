"use client";

import { useState } from "react";

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
        className="flex flex-col gap-3 sm:flex-row"
      >
        <input
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="Название университета, например «КБТУ»"
          aria-label="Название университета"
          className="w-full rounded-xl border border-[var(--border)] bg-[var(--surface)] px-4 py-3 text-base outline-none placeholder:text-[var(--muted)] focus:border-[var(--accent)]"
        />
        {busy ? (
          <button
            type="button"
            onClick={onCancel}
            className="rounded-xl border border-[var(--border)] bg-[var(--surface-2)] px-6 py-3 font-medium text-[var(--muted)] hover:text-[var(--foreground)]"
          >
            Отменить
          </button>
        ) : (
          <button
            type="submit"
            disabled={value.trim().length < 2}
            className="rounded-xl bg-[var(--accent)] px-6 py-3 font-semibold text-[#08111f] disabled:opacity-40"
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
            className="rounded-lg border border-[var(--border)] px-2 py-1 hover:border-[var(--accent)] hover:text-[var(--foreground)] disabled:opacity-40"
          >
            {e}
          </button>
        ))}
      </div>
    </div>
  );
}
