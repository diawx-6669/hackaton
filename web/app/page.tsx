"use client";

import { useRouter } from "next/navigation";
import { CandidatePicker } from "@/components/CandidatePicker";
import { Funnel } from "@/components/Funnel";
import {
  CategoriesStrip,
  HeroStats,
  HowItWorks,
  Pillars,
  SourcesNote,
  TrustFormula,
} from "@/components/Landing";
import { ProfileView } from "@/components/ProfileView";
import { SearchBar } from "@/components/SearchBar";
import { useProfileRun } from "@/lib/useProfile";

export default function Home() {
  const router = useRouter();
  const { events, profile, candidates, error, running, startedAt, run, cancel } = useProfileRun();
  const started = events.length > 0 || running;

  return (
    <main className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-4 py-6 sm:gap-10 sm:px-6 sm:py-12">
      {!started && (
        <section className="rise flex flex-col gap-4 sm:gap-5 sm:pt-6">
          <p className="w-fit rounded-full border border-[var(--border)] bg-[var(--surface)] px-3 py-1 text-xs text-[var(--muted)]">
            Хакатон LOCUS 2026 · кейс 1
          </p>
          <h1 className="max-w-4xl text-[28px] font-extrabold leading-[1.12] sm:text-5xl lg:text-6xl">
            Университеты показывают рекламу.
            <br />
            <span className="bg-gradient-to-r from-[var(--accent)] to-[#8b7bff] bg-clip-text text-transparent">
              CampusLens показывает, как там на самом деле.
            </span>
          </h1>
          <p className="max-w-2xl text-sm leading-relaxed text-[var(--muted)] sm:text-lg">
            Введите название вуза — меньше чем за 30 секунд соберём визуальный профиль кампуса
            из открытых источников: кампус, общежития, аудитории, библиотеки, лаборатории, спорт,
            студенческая жизнь и город.
          </p>
        </section>
      )}

      <SearchBar busy={running} onSearch={(q) => run({ q })} onCancel={cancel} />

      {!started && <HeroStats />}

      {error && (
        <p className="rounded-2xl border border-[var(--bad)]/40 bg-[var(--bad)]/5 p-4 text-sm text-[var(--bad)]">
          {error}
        </p>
      )}

      <Funnel events={events} running={running} startedAt={startedAt} />

      {candidates && !profile && (
        <CandidatePicker
          candidates={candidates}
          onPick={(u) => {
            // Постоянная ссылка на профиль: её можно отправить и открыть заново.
            router.push(`/u/${u.id}`);
          }}
        />
      )}

      {profile && <ProfileView profile={profile} />}

      {!started && (
        <>
          <Pillars />
          <HowItWorks />
          <TrustFormula />
          <CategoriesStrip />
          <SourcesNote />
        </>
      )}

      <footer className="mt-4 border-t border-[var(--border-soft)] pt-4 text-xs text-[var(--muted)]">
        Данные: Wikidata (CC0) и Wikimedia Commons — лицензия каждого файла указана в карточке.
        Карта: OpenStreetMap.{" "}
        <a
          href="https://github.com/diawx-6669/hackaton"
          target="_blank"
          rel="noopener noreferrer"
          className="text-[var(--accent)] underline"
        >
          Исходный код на GitHub
        </a>
        .
      </footer>
    </main>
  );
}
