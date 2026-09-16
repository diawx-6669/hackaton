"use client";

import { useRouter } from "next/navigation";
import { CandidatePicker } from "@/components/CandidatePicker";
import { Funnel } from "@/components/Funnel";
import { ProfileView } from "@/components/ProfileView";
import { SearchBar } from "@/components/SearchBar";
import { useProfileRun } from "@/lib/useProfile";

const PILLARS = [
  {
    title: "Только подтверждённое",
    text: "15 проверенных фото лучше 100 случайных. У каждого снимка — источник, автор и лицензия.",
  },
  {
    title: "Видно, почему поверили",
    text: "Балл достоверности разложен на улики: геотег, домен, привязка к вузу, свежесть.",
  },
  {
    title: "Честно про пустоту",
    text: "Если подтверждённых фото по категории нет — так и написано. Ничего не додумываем.",
  },
];

export default function Home() {
  const router = useRouter();
  const { events, profile, candidates, error, running, startedAt, run, cancel } = useProfileRun();
  const started = events.length > 0 || running;

  return (
    <main className="mx-auto flex w-full max-w-6xl flex-col gap-5 px-4 py-6 sm:gap-6 sm:px-6 sm:py-12">
      {!started && (
        <section className="flex flex-col gap-3 sm:gap-4 sm:pt-10">
          <p className="w-fit rounded-full border border-[var(--border)] bg-[var(--surface)] px-3 py-1 text-xs text-[var(--muted)]">
            Хакатон LOCUS 2026 · кейс 1
          </p>
          <h1 className="text-[26px] font-bold leading-[1.15] sm:text-5xl sm:leading-tight">
            Университеты показывают рекламу.
            <br />
            <span className="text-[var(--accent)]">CampusLens показывает, как там на самом деле.</span>
          </h1>
          <p className="max-w-2xl text-sm text-[var(--muted)] sm:text-lg">
            Введите название вуза — меньше чем за 30 секунд соберём визуальный профиль кампуса
            из открытых источников: кампус, общежития, аудитории, библиотеки, лаборатории, спорт,
            студенческая жизнь и город.
          </p>
        </section>
      )}

      <SearchBar busy={running} onSearch={(q) => run({ q })} onCancel={cancel} />

      {!started && (
        <section className="grid gap-3 sm:grid-cols-3">
          {PILLARS.map((p) => (
            <article
              key={p.title}
              className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-4"
            >
              <h2 className="font-semibold">{p.title}</h2>
              <p className="mt-1 text-sm text-[var(--muted)]">{p.text}</p>
            </article>
          ))}
        </section>
      )}

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

      <footer className="mt-6 border-t border-[var(--border)] pt-4 text-xs text-[var(--muted)]">
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
