"use client";

import dynamic from "next/dynamic";
import type { Surroundings as Data, University } from "@/lib/types";

// Leaflet обращается к window, поэтому карта грузится только в браузере.
const NearbyMap = dynamic(() => import("./NearbyMap"), {
  ssr: false,
  loading: () => <div className="h-[300px] w-full animate-pulse bg-[var(--surface-2)] sm:h-[380px]" />,
});

/**
 * «Жизнь в радиусе 15 минут» по данным OpenStreetMap (п.8 ТЗ).
 *
 * Карта показывается всегда, когда у вуза есть координаты, — даже если
 * Overpass промолчал. Раньше на его месте была строка «источник не ответил»,
 * и это худший вариант: человеку нужна карта, а не рассказ о наших проблемах.
 * Про недоступность источника блок всё равно сообщает, но тихо и внизу.
 *
 * В списке только то, что реально отмечено в OSM: что за объект, как далеко и
 * сколько идти. Ни цен, ни оценок безопасности — таких данных в открытых
 * источниках нет, а выдумывать их запрещено самим ТЗ.
 */
export function SurroundingsBlock({
  data,
  university,
}: {
  data: Data;
  university: University;
}) {
  const filled = data.groups.filter((g) => g.count > 0);
  const empty = data.groups.filter((g) => g.count === 0);
  const hasMap = Boolean(university.coordinates);

  return (
    <section className="overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--surface)]">
      <header className="flex flex-wrap items-baseline justify-between gap-2 p-4 pb-3 sm:p-5 sm:pb-3">
        <h2 className="text-base font-semibold sm:text-lg">Что рядом с кампусом</h2>
        <span className="text-xs text-[var(--muted)]">
          OpenStreetMap · радиус {data.radius_m} м
          {data.available ? ` · найдено ${data.total}` : ""}
        </span>
      </header>

      {hasMap ? (
        <NearbyMap university={university} groups={filled} radiusM={data.radius_m} />
      ) : (
        <p className="px-4 pb-3 text-sm text-[var(--muted)] sm:px-5">
          У вуза нет координат в Wikidata (P625) — карту показать не из чего.
        </p>
      )}

      <div className="p-4 sm:p-5">
        {filled.length > 0 && (
          <div className="grid gap-2 sm:grid-cols-2">
            {filled.map((g) => (
              <div key={g.key} className="rounded-xl bg-[var(--surface-2)] p-3">
                <div className="flex items-baseline justify-between gap-2">
                  <h3 className="text-sm font-medium">{g.title}</h3>
                  <span className="font-mono text-sm text-[var(--accent)]">{g.count}</span>
                </div>
                <ul className="mt-1.5 grid gap-1">
                  {g.nearest.map((p) => (
                    <li
                      key={p.osm_url}
                      className="flex items-baseline justify-between gap-2 text-xs"
                    >
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
          {!data.available
            ? "Список объектов рядом собрать не удалось — Overpass не ответил. Карта и координаты кампуса от этого не зависят. "
            : ""}
          Расстояние и время — по прямой от координат вуза, пешком 4,5 км/ч. Реальный путь
          длиннее: дороги, переходы и заборы здесь не учитываются.
        </p>
      </div>
    </section>
  );
}
