"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import { PhotoCard } from "@/components/PhotoCard";
import { compareUniversities } from "@/lib/api";
import type { Comparison, Profile } from "@/lib/types";

function Side({ profile, label }: { profile: Profile; label: string }) {
  const top = profile.verified.slice(0, 4);
  return (
    <div className="grid gap-3">
      <header className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-4">
        <p className="text-xs text-[var(--muted)]">{label}</p>
        <h2 className="text-lg font-semibold">{profile.university.name}</h2>
        <p className="mt-1 text-sm text-[var(--muted)]">
          {[profile.university.city, profile.university.country].filter(Boolean).join(", ") || "—"}
        </p>
        <Link
          href={`/u/${profile.university.id}`}
          className="mt-2 inline-block text-sm text-[var(--accent)] underline"
        >
          Полный профиль →
        </Link>
      </header>

      {top.length > 0 ? (
        <div className="grid grid-cols-2 gap-2">
          {top.map((p) => (
            <PhotoCard key={p.id} photo={p} />
          ))}
        </div>
      ) : (
        <p className="rounded-2xl border border-dashed border-[var(--border)] p-4 text-center text-sm text-[var(--muted)]">
          Подтверждённых фото не найдено
        </p>
      )}
    </div>
  );
}

export default function ComparePage() {
  const [a, setA] = useState("");
  const [b, setB] = useState("");
  const [result, setResult] = useState<Comparison | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setBusy(true);
    setError(null);
    setResult(null);
    try {
      setResult(await compareUniversities(a.trim(), b.trim(), controller.signal));
    } catch (err) {
      if ((err as Error).name !== "AbortError") setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto flex w-full max-w-6xl flex-col gap-5 px-4 py-8 sm:px-6 sm:py-10">
      <header>
        <h1 className="text-2xl font-bold sm:text-3xl">Сравнение двух вузов</h1>
        <p className="mt-2 max-w-2xl text-sm text-[var(--muted)]">
          Оба профиля собираются параллельно, поэтому сравнение занимает примерно столько же,
          сколько один профиль. Сравниваются только подтверждённые фото.
        </p>
      </header>

      <form onSubmit={submit} className="grid gap-3 sm:grid-cols-[1fr_1fr_auto]">
        <input
          value={a}
          onChange={(e) => setA(e.target.value)}
          placeholder="Первый вуз, например «КБТУ»"
          aria-label="Первый вуз"
          className="rounded-xl border border-[var(--border)] bg-[var(--surface)] px-4 py-3 outline-none placeholder:text-[var(--muted)] focus:border-[var(--accent)]"
        />
        <input
          value={b}
          onChange={(e) => setB(e.target.value)}
          placeholder="Второй вуз, например «Nazarbayev University»"
          aria-label="Второй вуз"
          className="rounded-xl border border-[var(--border)] bg-[var(--surface)] px-4 py-3 outline-none placeholder:text-[var(--muted)] focus:border-[var(--accent)]"
        />
        <button
          type="submit"
          disabled={busy || a.trim().length < 2 || b.trim().length < 2}
          className="w-full rounded-xl bg-[var(--accent)] px-6 py-3 font-semibold text-[#08111f] disabled:opacity-40 sm:w-auto"
        >
          {busy ? "Собираем…" : "Сравнить"}
        </button>
      </form>

      {busy && (
        <p className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-4 text-sm text-[var(--muted)]">
          Два профиля собираются одновременно — это до 30 секунд.
        </p>
      )}

      {error && (
        <p className="rounded-2xl border border-[var(--bad)]/40 bg-[var(--bad)]/5 p-4 text-sm text-[var(--bad)]">
          {error}
        </p>
      )}

      {result && (
        <>
          <section className="overflow-x-auto rounded-2xl border border-[var(--border)] bg-[var(--surface)]">
            <table className="w-full min-w-[520px] text-sm">
              <thead>
                <tr className="border-b border-[var(--border)] text-left text-[var(--muted)]">
                  <th className="px-4 py-3 font-normal">Показатель</th>
                  <th className="px-4 py-3">{result.a.university.name}</th>
                  <th className="px-4 py-3">{result.b.university.name}</th>
                </tr>
              </thead>
              <tbody>
                {result.rows.map((row) => (
                  <tr key={row.key} className="border-b border-[var(--border)] last:border-0">
                    <td className="px-4 py-3 text-[var(--muted)]">{row.label}</td>
                    <td
                      className={`px-4 py-3 font-medium ${row.winner === "a" ? "text-[var(--ok)]" : ""}`}
                    >
                      {row.a}
                    </td>
                    <td
                      className={`px-4 py-3 font-medium ${row.winner === "b" ? "text-[var(--ok)]" : ""}`}
                    >
                      {row.b}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="px-4 py-2 text-xs text-[var(--muted)]">
              Сравнение собрано за {(result.took_ms / 1000).toFixed(1)} с. Зелёным — где показатель
              выше; это про объём и качество найденных данных, а не оценка самого вуза.
            </p>
          </section>

          <section className="grid gap-4 lg:grid-cols-2">
            <Side profile={result.a} label="Вуз A" />
            <Side profile={result.b} label="Вуз B" />
          </section>
        </>
      )}
    </main>
  );
}
