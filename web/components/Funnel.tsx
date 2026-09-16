"use client";

import { useEffect, useState } from "react";
import type { StageEvent } from "@/lib/types";

const STAGE_TITLES: Record<string, string> = {
  collecting: "Сбор источников",
  resolved: "Вуз определён",
  found: "Найдено",
  deduped: "Дубли удалены",
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

/** Живая воронка: этапы от бэкенда + секундомер, который тикает в браузере. */
export function Funnel({ events, running, startedAt }: Props) {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (!running) return;
    const t = setInterval(() => setNow(Date.now()), 100);
    return () => clearInterval(t);
  }, [running]);

  if (events.length === 0 && !running) return null;

  const lastElapsed = events.length ? events[events.length - 1].elapsed_ms : 0;
  const elapsed = running && startedAt ? now - startedAt : lastElapsed;
  const seconds = (elapsed / 1000).toFixed(1);

  return (
    <section className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-4 sm:p-5">
      <header className="flex items-center justify-between gap-3">
        <h2 className="flex items-center gap-2 text-lg font-semibold">
          {running && (
            <span className="pulse-dot inline-block h-2.5 w-2.5 rounded-full bg-[var(--accent)]" />
          )}
          Воронка сборки
        </h2>
        <span className="font-mono text-xl tabular-nums text-[var(--accent)]">{seconds} с</span>
      </header>

      <ol className="mt-4 grid gap-2">
        {events.map((e, i) => (
          <li
            key={`${e.stage}-${i}`}
            className="flex flex-col gap-1 rounded-xl border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 sm:flex-row sm:items-center sm:justify-between"
          >
            <span className="flex flex-wrap items-center gap-2">
              <span
                className="rounded-md px-2 py-0.5 text-xs font-medium"
                style={{
                  background: "var(--background)",
                  color: STAGE_COLOR[e.stage] ?? "var(--accent)",
                }}
              >
                {STAGE_TITLES[e.stage] ?? e.stage}
              </span>
              <span className="text-sm">{e.message}</span>
            </span>
            <span className="font-mono text-xs tabular-nums text-[var(--muted)]">
              +{(e.elapsed_ms / 1000).toFixed(1)} с
            </span>
          </li>
        ))}
      </ol>
    </section>
  );
}
