"use client";

import { useState } from "react";
import { API_BASE } from "@/lib/api";

type Result = { ok: boolean; message: string; delivery: string };

/** Форма «не нашли свой вуз» — заявка на сбор данных. */
export function SubscribeForm({ presetUniversity = "" }: { presetUniversity?: string }) {
  const [email, setEmail] = useState("");
  const [university, setUniversity] = useState(presetUniversity);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const res = await fetch(`${API_BASE}/api/subscribe`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim(), university: university.trim() }),
      });
      const body = await res.json();
      if (!res.ok) {
        throw new Error(
          typeof body?.detail === "string" ? body.detail : "Не удалось отправить заявку",
        );
      }
      setResult(body);
      setEmail("");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (result) {
    return (
      <div className="rounded-xl border border-[var(--ok)]/40 bg-[var(--ok)]/10 p-4 text-sm">
        <p className="font-medium text-[var(--ok)]">Заявка принята</p>
        <p className="mt-1 text-[var(--muted)]">{result.message}</p>
        <button
          type="button"
          onClick={() => setResult(null)}
          className="mt-3 text-xs text-[var(--accent)] underline"
        >
          Отправить ещё одну
        </button>
      </div>
    );
  }

  return (
    <form onSubmit={submit} className="grid gap-3">
      <div>
        <h3 className="font-display text-lg font-semibold">Не нашли свой вуз?</h3>
        <p className="mt-1 text-xs leading-5 text-[var(--muted)]">
          Оставьте почту — пришлём отчёт, когда соберём по нему данные.
        </p>
      </div>

      <label className="grid gap-1 text-xs font-medium">
        Вуз
        <input
          value={university}
          onChange={(e) => setUniversity(e.target.value)}
          required
          minLength={2}
          maxLength={200}
          placeholder="Например, Актюбинский региональный университет"
          className="field h-11 rounded-lg bg-transparent px-3 text-sm font-normal outline-none placeholder:text-[var(--muted)]"
        />
      </label>

      <label className="grid gap-1 text-xs font-medium">
        Почта
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          placeholder="you@example.com"
          className="field h-11 rounded-lg bg-transparent px-3 text-sm font-normal outline-none placeholder:text-[var(--muted)]"
        />
      </label>

      {error && <p className="text-xs text-[var(--bad)]">{error}</p>}

      <button
        type="submit"
        disabled={busy || email.trim().length < 5 || university.trim().length < 2}
        className="primary-action h-11 rounded-lg font-semibold"
      >
        {busy ? "Отправляем…" : "Сообщить мне"}
      </button>

      <p className="text-[11px] leading-4 text-[var(--muted)]">
        Почта нужна только для этого отчёта. Рассылок и передачи третьим лицам нет.
      </p>
    </form>
  );
}
