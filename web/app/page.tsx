"use client";

import { useCallback, useRef, useState } from "react";
import { CandidatePicker } from "@/components/CandidatePicker";
import { Funnel } from "@/components/Funnel";
import { ProfileView } from "@/components/ProfileView";
import { SearchBar } from "@/components/SearchBar";
import { streamProfile } from "@/lib/api";
import type { Profile, StageEvent, University } from "@/lib/types";

export default function Home() {
  const [events, setEvents] = useState<StageEvent[]>([]);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [candidates, setCandidates] = useState<University[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const run = useCallback(async (params: { q?: string; id?: string }) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setEvents([]);
    setProfile(null);
    setCandidates(null);
    setError(null);
    setRunning(true);
    setStartedAt(Date.now());

    try {
      await streamProfile(
        params,
        (event) => {
          setEvents((prev) => [...prev, event]);

          if (event.stage === "resolved" && event.payload?.needs_choice) {
            setCandidates(event.payload.candidates as University[]);
          }
          if (event.stage === "done" && event.payload) {
            setProfile(event.payload as unknown as Profile);
          }
          if (event.stage === "error") {
            setError(event.message);
          }
        },
        controller.signal,
      );
    } catch (e) {
      if ((e as Error).name !== "AbortError") {
        setError(
          `${(e as Error).message}. Бэкенд поднят на ${process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"}?`,
        );
      }
    } finally {
      setRunning(false);
    }
  }, []);

  return (
    <main className="mx-auto flex w-full max-w-6xl flex-col gap-5 px-4 py-8 sm:px-6 sm:py-12">
      <header>
        <h1 className="text-2xl font-bold sm:text-4xl">
          CampusLens <span className="text-[var(--accent)]">AI</span>
        </h1>
        <p className="mt-2 max-w-2xl text-sm text-[var(--muted)] sm:text-base">
          Введите название вуза — сервис за считанные секунды соберёт визуальный профиль кампуса
          из открытых источников: с автором, лицензией, ссылкой на источник и разбором улик.
          Ничего не захардкожено: всё ищется на лету в Wikidata и Wikimedia Commons.
        </p>
      </header>

      <SearchBar
        busy={running}
        onSearch={(q) => run({ q })}
        onCancel={() => abortRef.current?.abort()}
      />

      {error && (
        <p className="rounded-2xl border border-[var(--bad)]/40 bg-[var(--bad)]/5 p-4 text-sm text-[var(--bad)]">
          {error}
        </p>
      )}

      <Funnel events={events} running={running} startedAt={startedAt} />

      {candidates && !profile && (
        <CandidatePicker candidates={candidates} onPick={(u) => run({ id: u.id })} />
      )}

      {profile && <ProfileView profile={profile} />}

      <footer className="mt-6 border-t border-[var(--border)] pt-4 text-xs text-[var(--muted)]">
        Данные: Wikidata (CC0) и Wikimedia Commons — лицензия каждого файла указана в карточке.
        Хакатон LOCUS 2026, кейс 1.
      </footer>
    </main>
  );
}
