"use client";

import { useState } from "react";
import { REJECT_LABELS, SOURCE_LABELS, type Photo } from "@/lib/types";

function confidenceColor(c: number): string {
  if (c >= 0.62) return "var(--ok)";
  if (c >= 0.38) return "var(--warn)";
  return "var(--bad)";
}

function hostOf(url: string): string {
  try {
    return new URL(url).hostname;
  } catch {
    return url;
  }
}

export function PhotoCard({ photo }: { photo: Photo }) {
  const [openEvidence, setOpenEvidence] = useState(false);
  const rejected = Boolean(photo.reject_reason);

  return (
    <article className="flex flex-col overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--surface)]">
      <a
        href={photo.source_page_url}
        target="_blank"
        rel="noopener noreferrer"
        className="relative block aspect-[4/3] bg-[var(--surface-2)]"
        title="Открыть страницу-источник"
      >
        <img
          src={photo.thumb_url || photo.url}
          alt={photo.title}
          loading="lazy"
          className={`h-full w-full object-cover ${rejected ? "opacity-50 grayscale" : ""}`}
        />
        {!rejected && (
          <span
            className="absolute right-2 top-2 rounded-lg bg-[#08111fdd] px-2 py-1 font-mono text-xs"
            style={{ color: confidenceColor(photo.confidence) }}
          >
            {Math.round(photo.confidence * 100)}%
          </span>
        )}
        {rejected && (
          <span className="absolute left-2 top-2 rounded-lg bg-[#08111fdd] px-2 py-1 text-xs text-[var(--bad)]">
            {REJECT_LABELS[photo.reject_reason!] ?? photo.reject_reason}
          </span>
        )}
      </a>

      <div className="flex flex-1 flex-col gap-2 p-3">
        <h3 className="line-clamp-2 text-sm font-medium" title={photo.title}>
          {photo.title}
        </h3>

        {rejected && photo.reject_detail && (
          <p className="text-xs text-[var(--bad)]">Причина: {photo.reject_detail}</p>
        )}

        <dl className="grid gap-1 text-xs text-[var(--muted)]">
          <div className="flex gap-1">
            <dt className="shrink-0">Автор:</dt>
            <dd className="truncate">{photo.author || "не указан"}</dd>
          </div>
          <div className="flex gap-1">
            <dt className="shrink-0">Лицензия:</dt>
            <dd className="truncate">
              {photo.license_url ? (
                <a
                  href={photo.license_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="underline hover:text-[var(--foreground)]"
                >
                  {photo.license}
                </a>
              ) : (
                photo.license || "не указана"
              )}
            </dd>
          </div>
          {photo.date && (
            <div className="flex gap-1">
              <dt className="shrink-0">Дата:</dt>
              <dd className="truncate">{photo.date}</dd>
            </div>
          )}
          <div className="flex flex-wrap gap-1">
            {photo.source_kinds.map((s) => (
              <span key={s} className="rounded-md bg-[var(--surface-2)] px-1.5 py-0.5">
                {SOURCE_LABELS[s] ?? s}
              </span>
            ))}
          </div>
        </dl>

        <div className="mt-auto flex flex-col gap-2 pt-1">
          <button
            type="button"
            onClick={() => setOpenEvidence((v) => !v)}
            className="self-start text-xs text-[var(--accent)] underline"
            aria-expanded={openEvidence}
          >
            {openEvidence ? "Скрыть улики" : "Показать улики"}
          </button>

          {openEvidence && (
            <div className="rounded-xl bg-[var(--surface-2)] p-2 text-xs">
              <ul className="grid gap-1.5">
                {photo.evidence.signals.map((s) => (
                  <li key={s.key}>
                    <div className="flex items-center justify-between gap-2">
                      <span>{s.label}</span>
                      <span className="font-mono text-[var(--muted)]">
                        {Math.round(s.value * 100)}% · вес {s.weight}
                      </span>
                    </div>
                    <div className="mt-0.5 h-1 w-full overflow-hidden rounded bg-[var(--background)]">
                      <div
                        className="h-full rounded bg-[var(--accent)]"
                        style={{ width: `${Math.max(2, s.value * 100)}%` }}
                      />
                    </div>
                    <p className="mt-0.5 text-[var(--muted)]">{s.detail}</p>
                  </li>
                ))}
              </ul>
              {photo.evidence.notes.length > 0 && (
                <ul className="mt-2 grid gap-1 border-t border-[var(--border)] pt-2 text-[var(--muted)]">
                  {photo.evidence.notes.map((n) => (
                    <li key={n}>· {n}</li>
                  ))}
                </ul>
              )}
            </div>
          )}

          <a
            href={photo.source_page_url}
            target="_blank"
            rel="noopener noreferrer"
            className="truncate text-xs text-[var(--accent)] underline"
          >
            Источник: {hostOf(photo.source_page_url)}
          </a>
        </div>
      </div>
    </article>
  );
}
