"use client";

import { useCallback, useRef, useState } from "react";
import { streamProfile } from "./api";
import type { Profile, StageEvent, University } from "./types";

/** Общая логика запуска конвейера: её используют и главная, и постоянная ссылка. */
export function useProfileRun() {
  const [events, setEvents] = useState<StageEvent[]>([]);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [candidates, setCandidates] = useState<University[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const cancel = useCallback(() => abortRef.current?.abort(), []);

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
        const base = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
        setError(`${(e as Error).message}. Бэкенд поднят на ${base}?`);
      }
    } finally {
      setRunning(false);
    }
  }, []);

  return { events, profile, candidates, error, running, startedAt, run, cancel };
}
