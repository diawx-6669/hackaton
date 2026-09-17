"use client";

import { useEffect } from "react";
import { CATEGORY_LABELS, REJECT_LABELS, SOURCE_LABELS, type Photo } from "@/lib/types";

export function Lightbox({ photo, onClose }: { photo: Photo; onClose: () => void }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [onClose]);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={photo.title}
      onClick={onClose}
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-[#040814ee] p-3 sm:p-6"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="grid w-full max-w-5xl gap-3 rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-2 sm:gap-4 sm:p-4 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]"
      >
        <img
          src={photo.url}
          alt={photo.title}
          className="max-h-[45vh] w-full rounded-xl object-contain sm:max-h-[70vh]"
        />

        <div className="flex flex-col gap-3 text-sm">
          <div className="flex items-start justify-between gap-2">
            <h3 className="text-base font-semibold">{photo.title}</h3>
            <button
              onClick={onClose}
              aria-label="Закрыть"
              className="shrink-0 rounded-lg border border-[var(--border)] px-2 py-1 text-xs text-[var(--muted)] hover:text-[var(--foreground)]"
            >
              <span className="hidden sm:inline">Esc </span>✕
            </button>
          </div>

          {photo.description && <p className="text-[var(--muted)]">{photo.description}</p>}

          <div className="flex flex-wrap gap-2 text-xs">
            <span className="rounded-lg bg-[var(--surface-2)] px-2 py-1">
              {CATEGORY_LABELS[photo.category]}
              {photo.category_source === "metadata" ? " · по метаданным" : ""}
            </span>
            {photo.reject_reason && (
              <span className="rounded-lg bg-[var(--bad)]/15 px-2 py-1 text-[var(--bad)]">
                {REJECT_LABELS[photo.reject_reason] ?? photo.reject_reason}
              </span>
            )}
          </div>

          <dl className="grid gap-1 text-xs text-[var(--muted)]">
            <div className="flex gap-1">
              <dt>Автор:</dt>
              <dd className="text-[var(--foreground)]">{photo.author || "не указан"}</dd>
            </div>
            <div className="flex gap-1">
              <dt>Лицензия:</dt>
              <dd className="text-[var(--foreground)]">{photo.license || "не указана"}</dd>
            </div>
            <div className="flex gap-1">
              <dt>Дата:</dt>
              <dd className="text-[var(--foreground)]">{photo.date || "не указана"}</dd>
            </div>
            <div className="flex gap-1">
              <dt>Размер:</dt>
              <dd className="text-[var(--foreground)]">
                {photo.width && photo.height ? `${photo.width}×${photo.height}` : "—"}
              </dd>
            </div>
            <div className="flex flex-wrap gap-1 pt-1">
              {photo.source_kinds.map((s) => (
                <span key={s} className="rounded-md bg-[var(--surface-2)] px-1.5 py-0.5">
                  {SOURCE_LABELS[s] ?? s}
                </span>
              ))}
            </div>
          </dl>

          <div className="rounded-xl bg-[var(--surface-2)] p-3">
            <div className="flex items-baseline justify-between">
              <span className="text-xs text-[var(--muted)]">Confidence Score</span>
              <span className="font-mono text-lg">{Math.round(photo.confidence * 100)}</span>
            </div>
            <ul className="mt-2 grid gap-2 text-xs">
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
              <ul className="mt-2 grid gap-1 border-t border-[var(--border)] pt-2 text-xs text-[var(--muted)]">
                {photo.evidence.notes.map((n) => (
                  <li key={n}>· {n}</li>
                ))}
              </ul>
            )}
          </div>

          <a
            href={photo.source_page_url}
            target="_blank"
            rel="noopener noreferrer"
            className="rounded-xl bg-[var(--accent)] px-4 py-2 text-center font-medium text-[#08111f]"
          >
            Открыть источник
          </a>
        </div>
      </div>
    </div>
  );
}
