"use client";

import type { Surroundings as Data } from "@/lib/types";

/**
 * «Жизнь в радиусе 15 минут» по данным OpenStreetMap (п.8 ТЗ).
 *
 * Здесь только то, что реально отмечено в OSM: что за объект, как далеко и
 * сколько идти. Ни цен, ни оценок безопасности — таких данных в открытых
 * источниках нет, а выдумывать их запрещено самим ТЗ.
 */
export function SurroundingsBlock({ data }: { data: Data }) {
  if (!data.available) {
    return (
      <section className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-4 sm:p-5">
        <h2 className="text-base font-semibold sm:text-lg">Что рядом с кампусом</h2>
        <p className="mt-2 text-sm text-[var(--warn)]">
          {data.error ?? "Источник не ответил"}
        </p>
      </section>
    );
  }

  const filled = data.groups.filter((g) => g.count > 0);
  const empty = data.groups.filter((g) => g.count === 0);

  return (
    <section className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-4 sm:p-5">
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-base font-semibold sm:text-lg">Что рядом с кампусом</h2>
        <span className="text-xs text-[var(--muted)]">
          OpenStreetMap · радиус {data.radius_m} м · найдено {data.total}
        </span>
      </header>

      {filled.length === 0 ? (
        <p className="mt-3 text-sm text-[var(--muted)]">
          В OpenStreetMap вокруг этих координат ничего не отмечено. Это говорит о полноте
          карты, а не о том, что рядом пусто.
        </p>
      ) : (
        <div className="mt-3 grid gap-2 sm:grid-cols-2">
          {filled.map((g) => (
            <div key={g.key} className="rounded-xl bg-[var(--surface-2)] p-3">
              <div className="flex items-baseline justify-between gap-2">
                <h3 className="text-sm font-medium">{g.title}</h3>
                <span className="font-mono text-sm text-[var(--accent)]">{g.count}</span>
              </div>
              <ul className="mt-1.5 grid gap-1">
                {g.nearest.map((p) => (
                  <li key={p.osm_url} className="flex items-baseline justify-between gap-2 text-xs">
                    <a
                      href={p.osm_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="truncate text-[var(--muted)] hover:text-[var(--foreground)] hover:underline"
                    >
                      {p.name || "без названия в OSM"}
                    </a>
                    <span className="shrink-0 font-mono text-[var(--muted)]">
                      {p.distance_m} м · {p.walk_minutes} мин
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}

      {empty.length > 0 && (
        <p className="mt-3 text-xs text-[var(--muted)]">
          Не отмечено в OSM: {empty.map((g) => g.title.toLowerCase()).join(", ")}.
        </p>
      )}

      <p className="mt-3 border-t border-[var(--border-soft)] pt-3 text-xs text-[var(--muted)]">
        Расстояние и время — по прямой от координат вуза, пешком 4,5 км/ч. Реальный путь
        длиннее: дороги, переходы и заборы здесь не учитываются.
      </p>
    </section>
  );
}
