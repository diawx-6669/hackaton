"use client";

import { useEffect, useMemo, useState } from "react";
import type { StageEvent } from "@/lib/types";

const STAGE_TITLES: Record<string, string> = {
  collecting: "Сбор источников",
  resolved: "Вуз определён",
  found: "Найдено",
  deduped: "Дубли удалены",
  classified: "Категории",
  described: "Описание",
  rejected: "Отклонено",
  verified: "Проверено",
  done: "Готово",
  error: "Ошибка",
};

const STAGE_COLOR: Record<string, string> = {
  error: "var(--bad)",
  rejected: "var(--warn)",
  done: "var(--ok)",
  verified: "var(--ok)",
};

type Props = {
  events: StageEvent[];
  running: boolean;
  startedAt: number | null;
};

/** Сжатая строка воронки из ТЗ: Найдено → Дубли → Отклонено → ✅ Проверено. */
function useSummary(events: StageEvent[]) {
  return useMemo(() => {
    const last = (stage: string) => [...events].reverse().find((e) => e.stage === stage);
    const found = last("found")?.counts.found;
    const deduped = last("deduped")?.counts.duplicates;
    const rejectedEvent = last("rejected");
    const verified = last("verified")?.counts.verified;

    if (found == null) return null;

    const steps: string[] = [`Найдено ${found}`];
    if (deduped) steps.push(`Дубли −${deduped}`);
    if (rejectedEvent) {
      const others = rejectedEvent.counts.rejected - (deduped ?? 0);
      if (others > 0) steps.push(`Отклонено −${others}`);
    }
    if (verified != null) steps.push(`✅ Проверено ${verified}`);
    return steps;
  }, [events]);
}

/** Живая воронка: этапы от бэкенда + секундомер, который тикает в браузере. */
export function Funnel({ events, running, startedAt }: Props) {
  const [now, setNow] = useState(() => Date.now());
  const [expanded, setExpanded] = useState(false);
  const summary = useSummary(events);

  useEffect(() => {
    if (!running) return;
    const t = setInterval(() => setNow(Date.now()), 100);
    return () => clearInterval(t);
  }, [running]);

  if (events.length === 0 && !running) return null;

  const lastElapsed = events.length ? events[events.length - 1].elapsed_ms : 0;
  const elapsed = running && startedAt ? now - startedAt : lastElapsed;
  const seconds = (elapsed / 1000).toFixed(1);

  // Пока идёт сбор — показываем этапы вживую. Когда закончили, сворачиваем
  // в одну строку: на телефоне одиннадцать строк съедали весь экран.
  const showSteps = running || expanded;

  return (
    <section className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-3 sm:p-5">
      <header className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
        <h2 className="flex items-center gap-2 text-base font-semibold sm:text-lg">
          {running && (
            <span className="pulse-dot inline-block h-2.5 w-2.5 shrink-0 rounded-full bg-[var(--accent)]" />
          )}
          Воронка сборки
        </h2>
        <span className="font-mono text-lg tabular-nums text-[var(--accent)] sm:text-xl">
          {seconds} с
        </span>
      </header>

      {!running && summary && (
        <p className="mt-2 flex flex-wrap items-center gap-x-1.5 gap-y-1 text-sm">
          {summary.map((step, i) => (
            <span key={step} className="flex items-center gap-1.5">
              {i > 0 && <span className="text-[var(--muted)]">→</span>}
              <span>{step}</span>
            </span>
          ))}
        </p>
      )}

      {!running && events.length > 0 && (
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          aria-expanded={expanded}
          className="mt-2 text-xs text-[var(--accent)] underline"
        >
          {expanded ? "Свернуть этапы" : `Показать все этапы (${events.length})`}
        </button>
      )}

      {showSteps && (
        <ol className="mt-3 grid gap-2">
          {events.map((e, i) => (
            <li
              key={`${e.stage}-${i}`}
              className="flex flex-col gap-1 rounded-xl border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 sm:flex-row sm:items-center sm:justify-between"
            >
              <span className="flex flex-wrap items-center gap-2">
                <span
                  className="shrink-0 rounded-md px-2 py-0.5 text-xs font-medium"
                  style={{
                    background: "var(--background)",
                    color: STAGE_COLOR[e.stage] ?? "var(--accent)",
                  }}
                >
                  {STAGE_TITLES[e.stage] ?? e.stage}
                </span>
                <span className="text-sm break-words">{e.message}</span>
              </span>
              <span className="shrink-0 font-mono text-xs tabular-nums text-[var(--muted)]">
                +{(e.elapsed_ms / 1000).toFixed(1)} с
              </span>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
