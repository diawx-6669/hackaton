"use client";

import type { University } from "@/lib/types";

type Props = {
  candidates: University[];
  onPick: (u: University) => void;
};

export function CandidatePicker({ candidates, onPick }: Props) {
  return (
    <section className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-4 sm:p-5">
      <h2 className="text-lg font-semibold">Уточните вуз</h2>
      <p className="mt-1 text-sm text-[var(--muted)]">
        Запрос подошёл нескольким записям в Wikidata — выберите нужную.
      </p>
      <ul className="mt-4 grid gap-2">
        {candidates.map((c) => (
          <li key={c.id}>
            <button
              onClick={() => onPick(c)}
              className="flex w-full flex-col gap-1 rounded-xl border border-[var(--border)] bg-[var(--surface-2)] p-3 text-left transition hover:border-[var(--accent)]"
            >
              <span className="flex flex-wrap items-center gap-2">
                <span className="font-medium">{c.name}</span>
                <span className="rounded-md bg-[var(--background)] px-2 py-0.5 text-xs text-[var(--muted)]">
                  {c.id}
                </span>
                <span className="text-xs text-[var(--muted)]">
                  совпадение {Math.round(c.match_score * 100)}%
                </span>
              </span>
              {c.description && (
                <span className="text-sm text-[var(--muted)]">{c.description}</span>
              )}
              <span className="flex flex-wrap gap-3 text-xs text-[var(--muted)]">
                {c.city && <span>📍 {c.city}{c.country ? `, ${c.country}` : ""}</span>}
                {c.coordinates && (
                  <span>
                    {c.coordinates.lat.toFixed(4)}, {c.coordinates.lon.toFixed(4)}
                  </span>
                )}
                {c.website && <span>🔗 {new URL(c.website).hostname}</span>}
                <span>{c.commons_category ? "🖼 есть категория Commons" : "🖼 нет категории Commons"}</span>
              </span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
