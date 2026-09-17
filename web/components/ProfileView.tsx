"use client";

import dynamic from "next/dynamic";
import { useMemo, useState } from "react";
import { CampusSummary } from "./CampusSummary";
import { Lightbox } from "./Lightbox";
import { PhotoCard } from "./PhotoCard";
import {
  CATEGORY_LABELS,
  REJECT_LABELS,
  type Photo,
  type PhotoCategory,
  type Profile,
} from "@/lib/types";

// Leaflet трогает window, поэтому карта грузится только на клиенте.
const CampusMap = dynamic(() => import("./CampusMap"), {
  ssr: false,
  loading: () => (
    <div className="h-[360px] animate-pulse rounded-2xl border border-[var(--border)] bg-[var(--surface)] sm:h-[440px]" />
  ),
});

type Tab = "verified" | "needs_review" | "rejected";

const TAB_TITLES: Record<Tab, string> = {
  verified: "Проверено",
  needs_review: "Требует проверки",
  rejected: "Отклонено",
};

const STAT_LABELS: Record<string, string> = {
  found: "найдено",
  unique: "уникальных",
  duplicates: "дублей",
  verified: "проверено",
  needs_review: "требуют проверки",
  rejected: "отклонено",
  sources: "источников",
};

// Фильтры из ТЗ (п.7) + кампус и город.
const FILTERS: PhotoCategory[] = [
  "campus",
  "dorms",
  "classrooms",
  "libraries",
  "labs",
  "sports",
  "student_life",
  "city",
];

export function ProfileView({ profile }: { profile: Profile }) {
  const [tab, setTab] = useState<Tab>("verified");
  const [category, setCategory] = useState<PhotoCategory | "all">("all");
  const [view, setView] = useState<"gallery" | "map">("gallery");
  const [lightbox, setLightbox] = useState<Photo | null>(null);

  const uni = profile.university;
  const photos = profile[tab];

  const filtered = useMemo(
    () => (category === "all" ? photos : photos.filter((p) => p.category === category)),
    [photos, category],
  );

  // empty_reason с бэкенда описывает ТОЛЬКО подтверждённые фото,
  // поэтому во вкладках «Требует проверки» и «Отклонено» он не годится.
  const bucket = profile.by_category.find((b) => b.category === category);
  const emptyNote =
    filtered.length !== 0
      ? null
      : tab === "verified" && category !== "all" && bucket?.empty_reason
        ? bucket.empty_reason
        : category !== "all"
          ? `В разделе «${TAB_TITLES[tab]}» нет фото категории «${CATEGORY_LABELS[category]}»`
          : `В разделе «${TAB_TITLES[tab]}» пока пусто`;

  const rejectSummary = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const p of profile.rejected) {
      const key = p.reject_reason ?? "unknown";
      counts[key] = (counts[key] ?? 0) + 1;
    }
    return counts;
  }, [profile.rejected]);

  return (
    <section className="grid gap-4">
      {/* Шапка вуза */}
      <header className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-4 sm:p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-xl font-semibold sm:text-2xl">{uni.name}</h2>
            <p className="mt-1 text-sm text-[var(--muted)]">
              {[uni.city, uni.country].filter(Boolean).join(", ") || "город не указан в Wikidata"}
              {uni.inception ? ` · основан ${uni.inception.slice(0, 4)}` : ""}
            </p>
          </div>
          <div className="flex flex-wrap gap-2 text-sm">
            {uni.website && (
              <a
                href={uni.website}
                target="_blank"
                rel="noopener noreferrer"
                className="rounded-lg border border-[var(--border)] px-3 py-1.5 hover:border-[var(--accent)]"
              >
                Сайт вуза
              </a>
            )}
            <a
              href={uni.wikidata_url}
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-lg border border-[var(--border)] px-3 py-1.5 hover:border-[var(--accent)]"
            >
              Wikidata {uni.id}
            </a>
            {uni.commons_category && (
              <a
                href={`https://commons.wikimedia.org/wiki/Category:${encodeURIComponent(uni.commons_category)}`}
                target="_blank"
                rel="noopener noreferrer"
                className="rounded-lg border border-[var(--border)] px-3 py-1.5 hover:border-[var(--accent)]"
              >
                Категория Commons
              </a>
            )}
          </div>
        </div>

        <dl className="mt-4 grid grid-cols-3 gap-2 sm:grid-cols-4 lg:grid-cols-8">
          {Object.entries(profile.stats).map(([key, value]) => (
            <div key={key} className="rounded-xl bg-[var(--surface-2)] px-2 py-2 sm:px-3">
              <dt className="text-[11px] leading-tight text-[var(--muted)] sm:text-xs">
                {STAT_LABELS[key] ?? key}
              </dt>
              <dd className="font-mono text-base sm:text-lg">{value}</dd>
            </div>
          ))}
          <div className="rounded-xl bg-[var(--surface-2)] px-2 py-2 sm:px-3">
            <dt className="text-[11px] leading-tight text-[var(--muted)] sm:text-xs">время</dt>
            <dd className="font-mono text-base sm:text-lg">
              {(profile.took_ms / 1000).toFixed(1)} с
            </dd>
          </div>
        </dl>

        {profile.warnings.length > 0 && (
          <ul className="mt-3 grid gap-1 rounded-xl border border-[var(--warn)]/40 bg-[var(--warn)]/5 p-3 text-sm text-[var(--warn)]">
            {profile.warnings.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        )}
      </header>

      {profile.description && <CampusSummary description={profile.description} />}
      {!profile.description && profile.partial && (
        <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-4">
          <p className="text-sm text-[var(--muted)]">
            Фото уже здесь. Описание кампуса дописывается по найденным источникам…
          </p>
          <div className="mt-3 grid gap-2">
            <div className="h-3 w-full animate-pulse rounded bg-[var(--surface-2)]" />
            <div className="h-3 w-4/5 animate-pulse rounded bg-[var(--surface-2)]" />
          </div>
        </div>
      )}

      {/* Галерея или карта */}
      <div className="flex flex-wrap gap-2">
        {(["gallery", "map"] as const).map((v) => (
          <button
            key={v}
            onClick={() => setView(v)}
            className={`rounded-xl border px-3 py-2 text-sm ${
              view === v
                ? "border-[var(--accent)] bg-[var(--surface-2)]"
                : "border-[var(--border)] text-[var(--muted)] hover:text-[var(--foreground)]"
            }`}
          >
            {v === "gallery" ? "Галерея" : "Карта"}
          </button>
        ))}
      </div>

      {view === "map" ? (
        <CampusMap
          university={uni}
          photos={[...profile.verified, ...profile.needs_review]}
        />
      ) : (
        <>
      {/* Вкладки: на телефоне лента с прокруткой, иначе «Отклонено»
          уезжало на отдельную строку во всю ширину. */}
      <div className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-1 sm:mx-0 sm:flex-wrap sm:overflow-visible sm:px-0">
        {(Object.keys(TAB_TITLES) as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`shrink-0 whitespace-nowrap rounded-xl border px-3 py-2 text-xs sm:px-3 sm:text-sm ${
              tab === t
                ? "border-[var(--accent)] bg-[var(--surface-2)]"
                : "border-[var(--border)] text-[var(--muted)] hover:text-[var(--foreground)]"
            }`}
          >
            {TAB_TITLES[t]} · {profile[t].length}
          </button>
        ))}
      </div>

      {/* Фильтры по категориям: на телефоне — прокручиваемая лента,
          на широком экране обычный перенос по строкам. */}
      <div className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-1 text-sm sm:mx-0 sm:flex-wrap sm:overflow-visible sm:px-0">
        <button
          onClick={() => setCategory("all")}
          className={`shrink-0 whitespace-nowrap rounded-lg border px-2.5 py-1.5 ${
            category === "all"
              ? "border-[var(--accent)]"
              : "border-[var(--border)] text-[var(--muted)]"
          }`}
        >
          Все
        </button>
        {FILTERS.map((c) => {
          const count = photos.filter((p) => p.category === c).length;
          return (
            <button
              key={c}
              onClick={() => setCategory(c)}
              className={`shrink-0 whitespace-nowrap rounded-lg border px-2.5 py-1.5 ${
                category === c
                  ? "border-[var(--accent)]"
                  : "border-[var(--border)] text-[var(--muted)]"
              }`}
            >
              {CATEGORY_LABELS[c]} · {count}
            </button>
          );
        })}
      </div>

      {tab === "rejected" && profile.rejected.length > 0 && (
        <ul className="flex flex-wrap gap-2 text-xs text-[var(--muted)]">
          {Object.entries(rejectSummary).map(([reason, count]) => (
            <li key={reason} className="rounded-lg bg-[var(--surface-2)] px-2 py-1">
              {REJECT_LABELS[reason] ?? reason}: {count}
            </li>
          ))}
        </ul>
      )}

      {emptyNote ? (
        <p className="rounded-2xl border border-dashed border-[var(--border)] bg-[var(--surface)] p-6 text-center text-sm text-[var(--muted)]">
          {emptyNote}
        </p>
      ) : (
        <div className="grid grid-cols-2 gap-2 sm:gap-3 lg:grid-cols-3 xl:grid-cols-4">
          {filtered.map((p) => (
            <PhotoCard key={`${tab}-${p.id}`} photo={p} onOpen={setLightbox} />
          ))}
        </div>
      )}
        </>
      )}

      {lightbox && <Lightbox photo={lightbox} onClose={() => setLightbox(null)} />}
    </section>
  );
}
