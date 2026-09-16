"use client";

import { useRouter } from "next/navigation";
import { CandidatePicker } from "@/components/CandidatePicker";
import { Funnel } from "@/components/Funnel";
import { ProfileView } from "@/components/ProfileView";
import { SearchPanel } from "@/components/SearchPanel";
import { useProfileRun } from "@/lib/useProfile";

export default function Home() {
  const router = useRouter();
  const { events, profile, candidates, error, running, startedAt, run, cancel } = useProfileRun();
  const started = events.length > 0 || running;

  // Пока поиск не запущен — экран входа: заголовок и стеклянная панель.
  if (!started) {
    return (
      <main className="mx-auto grid w-full max-w-[1440px] items-center gap-10 px-5 py-10 sm:px-10 lg:min-h-[calc(100dvh-4.5rem)] lg:grid-cols-[minmax(0,1fr)_440px] lg:gap-20 lg:px-16 lg:py-14">
        <div className="rise max-w-[640px]">
          <p className="w-fit rounded-full border border-[var(--border)] bg-[oklch(0.2_0.04_262_/_55%)] px-3 py-1 text-xs text-[var(--muted)] backdrop-blur">
            Хакатон LOCUS 2026 · кейс 1
          </p>

          <h1 className="font-display mt-5 text-[clamp(2.6rem,5.2vw,5.2rem)] font-medium leading-[0.98]">
            Кампус,
            <br />
            который виден честно.
          </h1>

          <p className="mt-5 max-w-md text-sm leading-6 text-[var(--muted)] sm:text-base">
            Визуальный профиль университета по реальным данным — вместо рекламных обещаний.
            У каждого снимка есть источник, автор и лицензия.
          </p>

          {error && (
            <p className="mt-6 max-w-md rounded-xl border border-[var(--bad)]/40 bg-[var(--bad)]/10 p-3 text-sm text-[var(--bad)]">
              {error}
            </p>
          )}
        </div>

        <div className="rise">
          <SearchPanel busy={running} onSearch={(q) => run({ q })} onCancel={cancel} />
        </div>
      </main>
    );
  }

  // Поиск пошёл — показываем воронку, выбор вуза и собранный профиль.
  return (
    <main className="mx-auto flex w-full max-w-6xl flex-col gap-5 px-4 py-6 sm:px-6 sm:py-10">
      <SearchPanel compact busy={running} onSearch={(q) => run({ q })} onCancel={cancel} />

      {error && (
        <p className="rounded-2xl border border-[var(--bad)]/40 bg-[var(--bad)]/10 p-4 text-sm text-[var(--bad)]">
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
