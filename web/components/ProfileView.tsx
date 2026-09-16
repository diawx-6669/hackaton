"use client";

import { useMemo, useState } from "react";
import { PhotoCard } from "./PhotoCard";
import { CATEGORY_LABELS, REJECT_LABELS, type PhotoCategory, type Profile } from "@/lib/types";

type Tab = "verified" | "needs_review" | "rejected";

const TAB_TITLES: Record<Tab, string> = {
  verified: "Проверено",
  needs_review: "⚠️ Требует проверки",
  rejected: "Отклонено",
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

  const uni = profile.university;
  const photos = profile[tab];

  const filtered = useMemo(
    () => (category === "all" ? photos : photos.filter((p) => p.category === category)),
    [photos, category],
  );

  const bucket = profile.by_category.find((b) => b.category === category);
  const emptyNote =
    filtered.length === 0
      ? category !== "all" && bucket?.empty_reason
        ? bucket.empty_reason
        : `В разделе «${TAB_TITLES[tab]}» пока пусто`
      : null;

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

        <dl className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-7">
          {Object.entries(profile.stats).map(([key, value]) => (
            <div key={key} className="rounded-xl bg-[var(--surface-2)] px-3 py-2">
              <dt className="text-xs text-[var(--muted)]">{key}</dt>
              <dd className="font-mono text-lg">{value}</dd>
            </div>
          ))}
          <div className="rounded-xl bg-[var(--surface-2)] px-3 py-2">
            <dt className="text-xs text-[var(--muted)]">время</dt>
            <dd className="font-mono text-lg">{(profile.took_ms / 1000).toFixed(1)} с</dd>
          </div>
        </dl>

        {profile.warnings.length > 0 && (
          <ul className="mt-3 grid gap-1 rounded-xl border border-[var(--warn)]/40 bg-[var(--warn)]/5 p-3 text-sm text-[var(--warn)]">
            {profile.warnings.map((w) => (
              <li key={w}>⚠️ {w}</li>
            ))}
          </ul>
        )}
      </header>

      {/* Вкладки */}
      <div className="flex flex-wrap gap-2">
        {(Object.keys(TAB_TITLES) as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`rounded-xl border px-3 py-2 text-sm ${
              tab === t
                ? "border-[var(--accent)] bg-[var(--surface-2)]"
                : "border-[var(--border)] text-[var(--muted)] hover:text-[var(--foreground)]"
            }`}
          >
            {TAB_TITLES[t]} · {profile[t].length}
          </button>
        ))}
      </div>

      {/* Фильтры по категориям */}
      <div className="flex flex-wrap gap-2 text-sm">
        <button
          onClick={() => setCategory("all")}
          className={`rounded-lg border px-2.5 py-1 ${
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
              className={`rounded-lg border px-2.5 py-1 ${
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
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {filtered.map((p) => (
            <PhotoCard key={`${tab}-${p.id}`} photo={p} />
          ))}
        </div>
      )}
    </section>
  );
}
