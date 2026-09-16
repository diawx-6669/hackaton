"use client";

import { useState } from "react";
import type { CampusDescription } from "@/lib/types";

/**
 * Описание кампуса от LLM. Показываем не только текст, но и на чём он
 * основан: каждое утверждение с кликабельным источником. Если описание
 * не подтверждено источниками — не показываем его вовсе.
 */
export function CampusSummary({ description }: { description: CampusDescription }) {
  const [openSources, setOpenSources] = useState(false);

  if (description.insufficient_data && description.claims.length === 0) {
    return (
      <section className="card p-4 text-sm text-[var(--muted)] sm:p-5">
        Найденных данных не хватило, чтобы честно описать кампус. Ниже — только фотографии
        с проверяемыми источниками.
      </section>
    );
  }

  return (
    <section className="card p-4 sm:p-5">
      <header className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-display text-lg font-semibold sm:text-xl">О кампусе</h2>
        <span className="rounded-lg bg-[var(--surface-2)] px-2 py-1 text-[11px] text-[var(--muted)]">
          написано по найденным источникам
        </span>
      </header>

      <p className="mt-3 text-sm leading-relaxed">{description.summary}</p>

      {description.insufficient_data && (
        <p className="mt-2 text-xs text-[var(--warn)]">
          Данных немного — описание получилось коротким. Это честнее, чем додумывать.
        </p>
      )}

      {description.unverified_claims.length > 0 && (
        <p className="mt-2 text-xs text-[var(--bad)]">
          Отброшено утверждений без источника: {description.unverified_claims.length}. В текст
          они не попали.
        </p>
      )}

      {description.claims.length > 0 && (
        <>
          <button
            type="button"
            onClick={() => setOpenSources((v) => !v)}
            aria-expanded={openSources}
            className="mt-3 text-xs text-[var(--accent)] underline"
          >
            {openSources
              ? "Скрыть источники"
              : `На чём это основано (${description.claims.length})`}
          </button>

          {openSources && (
            <ul className="mt-2 grid gap-2 border-t border-[var(--border-soft)] pt-3 text-xs">
              {description.claims.map((c, i) => (
                <li key={`${c.source_id}-${i}`} className="grid gap-0.5">
                  <span>{c.claim}</span>
                  <a
                    href={c.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="truncate text-[var(--accent)] underline"
                  >
                    источник: {c.source_id}
                  </a>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </section>
  );
}
