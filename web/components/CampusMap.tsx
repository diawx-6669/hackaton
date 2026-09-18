"use client";

import { useEffect, useMemo, useRef } from "react";
import type { Map as LeafletMap } from "leaflet";
import type { Photo, University } from "@/lib/types";

/**
 * Карта OpenStreetMap с точками фото (п.8 ТЗ).
 * Leaflet обращается к window, поэтому подключается динамически на клиенте,
 * а страница импортирует этот компонент через next/dynamic с ssr: false.
 */
export default function CampusMap({
  university,
  photos,
}: {
  university: University;
  photos: Photo[];
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<LeafletMap | null>(null);

  const geotagged = useMemo(() => photos.filter((p) => p.coordinates), [photos]);
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
        zoom: 16,
        scrollWheelZoom: false,
      });
      mapRef.current = map;

      // Тёмная подложка CARTO поверх данных OpenStreetMap: светлая стандартная
      // плитка на тёмной странице выглядит дырой. Атрибуция обязательна для
      // обоих — и для данных OSM, и для оформления CARTO.
      L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
        attribution:
          '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>, ' +
          '© <a href="https://carto.com/attributions">CARTO</a>',
        subdomains: "abcd",
        maxZoom: 20,
      }).addTo(map);

      const campusIcon = L.divIcon({
        className: "",
        html: `<div style="width:18px;height:18px;border-radius:50%;background:#38bdf8;border:3px solid #08111f;box-shadow:0 0 0 2px #38bdf8"></div>`,
        iconSize: [18, 18],
        iconAnchor: [9, 9],
      });
      L.marker([campus.lat, campus.lon], { icon: campusIcon })
        .addTo(map)
        .bindPopup(`<b>${university.name}</b><br/>координаты кампуса из Wikidata`);

      const bounds = L.latLngBounds([[campus.lat, campus.lon]]);

      for (const photo of geotagged) {
        const c = photo.coordinates!;
        const color =
          photo.confidence >= 0.62 ? "#34d399" : photo.confidence >= 0.38 ? "#fbbf24" : "#f87171";
        const marker = L.circleMarker([c.lat, c.lon], {
          radius: 7,
          color: "#08111f",
          weight: 2,
          fillColor: color,
          fillOpacity: 0.95,
        }).addTo(map);

        const distance = photo.evidence.geo_distance_m;
        marker.bindPopup(
          `<div style="max-width:200px">
             <img src="${photo.thumb_url ?? photo.url}" alt="" style="width:100%;border-radius:6px"/>
             <div style="margin-top:6px;font-weight:600">${photo.title}</div>
             <div>Достоверность: ${Math.round(photo.confidence * 100)}%</div>
             ${distance != null ? `<div>${Math.round(distance)} м до кампуса</div>` : ""}
             <a href="${photo.source_page_url}" target="_blank" rel="noopener noreferrer">Источник</a>
           </div>`,
        );
        bounds.extend([c.lat, c.lon]);
      }

      if (geotagged.length > 0) {
        map.fitBounds(bounds, { padding: [40, 40], maxZoom: 17 });
      }
    })();

    return () => {
      cancelled = true;
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, [campus, geotagged, university.name]);

  if (!campus) {
    return (
      <p className="rounded-2xl border border-dashed border-[var(--border)] bg-[var(--surface)] p-6 text-center text-sm text-[var(--muted)]">
        У вуза нет координат в Wikidata (P625) — карту показать не из чего.
      </p>
    );
  }

  return (
    <div className="overflow-hidden rounded-2xl border border-[var(--border)]">
      <div ref={containerRef} className="h-[360px] w-full sm:h-[440px]" />
      <div className="flex flex-wrap items-center gap-3 bg-[var(--surface)] px-4 py-2 text-xs text-[var(--muted)]">
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-2.5 w-2.5 rounded-full bg-[var(--accent)]" /> кампус
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-2.5 w-2.5 rounded-full bg-[var(--ok)]" /> проверено
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-2.5 w-2.5 rounded-full bg-[var(--warn)]" /> требует проверки
        </span>
        <span className="ml-auto">
          {geotagged.length > 0
            ? `${geotagged.length} фото с геотегом из ${photos.length}`
            : "ни у одного фото нет геотега"}
        </span>
      </div>
    </div>
  );
}
