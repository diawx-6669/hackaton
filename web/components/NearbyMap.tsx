"use client";

import { useEffect, useRef } from "react";
import type { Map as LeafletMap } from "leaflet";
import type { SurroundingGroup, University } from "@/lib/types";

/** Цвет точки по группе — тот же язык, что и в списке под картой. */
const GROUP_COLORS: Record<string, string> = {
  transport: "#38bdf8",
  food: "#fbbf24",
  groceries: "#a3e635",
  health: "#f87171",
  study: "#c084fc",
  sports: "#34d399",
  green: "#4ade80",
  dorms: "#f0abfc",
};

/**
 * Карта окружения кампуса.
 *
 * Показывается всегда, когда у вуза есть координаты, — даже если Overpass
 * промолчал и объектов рядом нет. Пустая карта с кампусом и кругом
 * пятнадцатиминутной доступности полезнее строки «источник не ответил»:
 * человек хотя бы видит, где вуз находится.
 */
export default function NearbyMap({
  university,
  groups,
  radiusM,
}: {
  university: University;
  groups: SurroundingGroup[];
  radiusM: number;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<LeafletMap | null>(null);
  const campus = university.coordinates;

  useEffect(() => {
    if (!campus || !containerRef.current || mapRef.current) return;
    let cancelled = false;

    (async () => {
      const L = (await import("leaflet")).default;
      await import("leaflet/dist/leaflet.css");
      if (cancelled || !containerRef.current) return;

      const map = L.map(containerRef.current, {
        center: [campus.lat, campus.lon],
        zoom: 15,
        scrollWheelZoom: false,
      });
      mapRef.current = map;

      // Штатная плитка OpenStreetMap: ключ не нужен, условия — только
      // атрибуция. Тёмной она становится фильтром в CSS (класс dark-tiles),
      // потому что подложки с готовой тёмной темой требуют платного ключа —
      // на это мы и напоролись, поставив CARTO: карта уехала в продакшен с
      // водяным знаком «API KEY REQUIRED» по всей площади.
      L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
        className: "dark-tiles",
        maxZoom: 19,
      }).addTo(map);

      // Круг доступности: ровно тот радиус, в котором мы искали объекты.
      const circle = L.circle([campus.lat, campus.lon], {
        radius: radiusM,
        color: "#38bdf8",
        weight: 1,
        opacity: 0.5,
        fillColor: "#38bdf8",
        fillOpacity: 0.05,
      }).addTo(map);

      const campusIcon = L.divIcon({
        className: "",
        html: `<div style="width:18px;height:18px;border-radius:50%;background:#38bdf8;border:3px solid #08111f;box-shadow:0 0 0 2px #38bdf8"></div>`,
        iconSize: [18, 18],
        iconAnchor: [9, 9],
      });
      L.marker([campus.lat, campus.lon], { icon: campusIcon })
        .addTo(map)
        .bindPopup(`<b>${university.name}</b><br/>координаты из Wikidata`);

      for (const group of groups) {
        const color = GROUP_COLORS[group.key] ?? "#94a3b8";
        for (const place of group.nearest) {
          if (!place.coordinates) continue;
          L.circleMarker([place.coordinates.lat, place.coordinates.lon], {
            radius: 6,
            color: "#08111f",
            weight: 2,
            fillColor: color,
            fillOpacity: 0.95,
          })
            .addTo(map)
            .bindPopup(
              `<div style="max-width:220px">
                 <div style="font-weight:600">${place.name || "без названия в OSM"}</div>
                 <div>${group.title} · ${place.distance_m} м · ${place.walk_minutes} мин пешком</div>
                 <a href="${place.osm_url}" target="_blank" rel="noopener noreferrer">Объект в OSM</a>
               </div>`,
            );
        }
      }

      // Круг целиком в кадре — иначе непонятно, какую территорию мы смотрели.
      map.fitBounds(circle.getBounds(), { padding: [20, 20] });
    })();

    return () => {
      cancelled = true;
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, [campus, groups, radiusM, university.name]);

  if (!campus) return null;

  return <div ref={containerRef} className="h-[300px] w-full sm:h-[380px]" />;
}
