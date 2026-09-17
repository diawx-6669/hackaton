"use client";

import { use, useEffect } from "react";
import Link from "next/link";
import { AuthGate } from "@/components/AuthGate";
import { Funnel } from "@/components/Funnel";
import { ProfileView } from "@/components/ProfileView";
import { useProfileRun } from "@/lib/useProfile";

/** Постоянная ссылка на профиль вуза: /u/Q1798175 — можно делиться и открывать заново. */
export default function UniversityPage({ params }: { params: Promise<{ qid: string }> }) {
  const { qid } = use(params);
  const { events, profile, error, running, startedAt, run } = useProfileRun();

  useEffect(() => {
    if (/^Q\d+$/.test(qid)) run({ id: qid });
  }, [qid, run]);

  if (!/^Q\d+$/.test(qid)) {
    return (
      <main className="mx-auto w-full max-w-6xl px-4 py-12 sm:px-6">
        <p className="rounded-2xl border border-[var(--bad)]/40 bg-[var(--bad)]/5 p-4 text-sm text-[var(--bad)]">
          «{qid}» не похож на Wikidata QID (ожидается вид Q1798175).
        </p>
        <Link href="/" className="mt-4 inline-block text-sm text-[var(--accent)] underline">
          ← к поиску
        </Link>
      </main>
    );
  }

  return (
    <main className="mx-auto flex w-full max-w-6xl flex-col gap-5 px-4 py-8 sm:px-6 sm:py-10">
      <Link href="/" className="w-fit text-sm text-[var(--accent)] underline">
        ← новый поиск
      </Link>

      {error && (
        <p className="rounded-2xl border border-[var(--bad)]/40 bg-[var(--bad)]/5 p-4 text-sm text-[var(--bad)]">
          {error}
        </p>
      )}

      <AuthGate>
        <Funnel events={events} running={running} startedAt={startedAt} />
        {profile && <ProfileView profile={profile} />}
      </AuthGate>
    </main>
  );
}
