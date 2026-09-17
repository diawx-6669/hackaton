"use client";

import type { DistrictInfo, Logistics } from "@/lib/types";

/**
 * Район и дорога. Ровно те факты, что отмечены в OpenStreetMap.
 *
 * Здесь намеренно НЕТ сводной оценки безопасности. Её пришлось бы собирать из
 * данных, которых в открытых источниках нет: охрана на входе, реальная
 * освещённость двора, ночная обстановка. Цифра выглядела бы авторитетно, а
 * была бы выдумана — и это была бы выдумка про реальный район, где живут люди.
 * Поэтому показываем счётчики и честно говорим, сколько улиц вообще без тега.
 */
export function DistrictBlock({
  district,
  logistics,
}: {
  district?: DistrictInfo | null;
  logistics?: Logistics | null;
}) {
  if (!district && !logistics) return null;

  return (
    <section className="grid gap-4 sm:grid-cols-2">
      {district && (
        <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-4 sm:p-5">
          <header className="flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="text-base font-semibold sm:text-lg">Инфраструктура района</h2>
            <span className="text-xs text-[var(--muted)]">OSM · {district.radius_m} м</span>
          </header>

          {!district.available ? (
            <p className="mt-2 text-sm text-[var(--warn)]">{district.error}</p>
          ) : (
            <>
              <dl className="mt-3 grid grid-cols-2 gap-2">
                <Stat
                  label="улиц помечены освещёнными"
                  value={
                    district.lit_share_percent == null
                      ? "нет данных"
                      : `${district.streets_lit} из ${district.streets_lit + district.streets_unlit}`
                  }
                />
                <Stat label="фонарей отмечено" value={district.street_lamps} />
                <Stat label="пешеходных переходов" value={district.crossings} />
                <Stat
                  label="ближайшая полиция"
                  value={district.police ? `${district.police.distance_m} м` : "не отмечена"}
                />
              </dl>

              {district.police?.name && (
                <a
                  href={district.police.osm_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-2 block text-xs text-[var(--accent)] hover:underline"
                >
                  {district.police.name}
                </a>
              )}

              <p className="mt-3 border-t border-[var(--border-soft)] pt-3 text-xs text-[var(--muted)]">
                {district.streets_without_lit_tag > 0 && (
                  <>
                    У {district.streets_without_lit_tag} из {district.streets_total} улиц тег
                    освещения в OSM не проставлен — это неизвестность, а не темнота.{" "}
                  </>
                )}
                Сводной оценки безопасности мы не выводим: данных о ней
                (охрана, реальная освещённость, ночная обстановка) в открытых источниках нет,
                а придуманный балл про настоящий район — худшее, что тут можно сделать.
              </p>
            </>
          )}
        </div>
      )}

      {logistics && (
        <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-4 sm:p-5">
          <h2 className="text-base font-semibold sm:text-lg">Сколько добираться</h2>

          {logistics.legs.length === 0 ? (
            <p className="mt-2 text-sm text-[var(--muted)]">
              {logistics.error ?? "Нечего посчитать"}
            </p>
          ) : (
            <ul className="mt-3 grid gap-2">
              {logistics.legs.map((leg) => (
                <li key={leg.key} className="rounded-xl bg-[var(--surface-2)] p-3">
                  <div className="flex items-baseline justify-between gap-2">
                    <span className="text-sm">{leg.title}</span>
                    <span className="shrink-0 font-mono text-sm text-[var(--accent)]">
                      {leg.minutes} мин
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-[var(--muted)]">
                    {(leg.distance_m / 1000).toFixed(1)} км ·{" "}
                    {leg.mode === "driving" ? "маршрут OSRM" : "оценка по прямой"}
                  </p>
                  <p className="mt-0.5 text-[11px] text-[var(--muted)]">{leg.note}</p>
                </li>
              ))}
            </ul>
          )}

          <p className="mt-3 border-t border-[var(--border-soft)] pt-3 text-xs text-[var(--muted)]">
            У публичного OSRM есть только автомобильный профиль, поэтому пеший участок —
            расстояние по прямой, а не реальный маршрут. Так и подписано.
          </p>
        </div>
      )}
    </section>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-xl bg-[var(--surface-2)] px-3 py-2">
      <dt className="text-[11px] leading-tight text-[var(--muted)]">{label}</dt>
      <dd className="font-mono text-base">{value}</dd>
    </div>
  );
}
