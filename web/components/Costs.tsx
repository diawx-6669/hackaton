"use client";

import type { Costs } from "@/lib/types";

/**
 * Стоимость жизни — дословные строки с сайта вуза.
 *
 * «Средний чек в столовой» и «аренда однушки рядом» мы не показываем: открытого
 * проверяемого источника таких цен нет, и любая цифра была бы выдумкой,
 * поданной как факт. Здесь только то, что вуз написал о себе сам, дословно и со
 * ссылкой на страницу. Не написал — так и сказано.
 */
export function CostsBlock({ data }: { data: Costs }) {
  return (
    <section className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-4 sm:p-5">
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-base font-semibold sm:text-lg">Сколько это стоит</h2>
        <span className="text-xs text-[var(--muted)]">цитаты с официального сайта</span>
      </header>

      {!data.available ? (
        <p className="mt-2 text-sm text-[var(--muted)]">{data.note}</p>
      ) : (
        <ul className="mt-3 grid gap-2">
          {data.quotes.map((q) => (
            <li key={q.quote} className="rounded-xl bg-[var(--surface-2)] p-3">
              <span className="text-xs text-[var(--accent)]">{q.topic_title}</span>
              <p className="mt-1 text-sm">«{q.quote}»</p>
              <a
                href={q.url}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-1 block truncate text-xs text-[var(--muted)] hover:underline"
              >
                {q.page_title} · {q.url}
              </a>
            </li>
          ))}
        </ul>
      )}

      <p className="mt-3 border-t border-[var(--border-soft)] pt-3 text-xs text-[var(--muted)]">
        Цитаты приводятся как есть: мы ничего не пересчитываем, не усредняем и не переводим
        в другую валюту. Цены на сайте вуза могли устареть — проверяйте по ссылке.
      </p>
    </section>
  );
}
