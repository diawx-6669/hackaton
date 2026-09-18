"use client";

import { useEffect, useState } from "react";
import type { CampusDescription, University } from "@/lib/types";

/**
 * Что известно про вуз.
 *
 * Работает БЕЗ языковой модели: факты берутся прямо из Wikidata, у каждого
 * есть ссылка на карточку вуза, где его можно проверить. Описание от LLM, если
 * оно собралось, показывается рядом — но блок не пустеет, когда ключа нет или
 * модель не ответила.
 *
 * Аудиообзор читает ровно этот текст через встроенный в браузер синтез речи.
 * Никакого нового содержания он не придумывает — иначе это были бы факты,
 * которых нет в источниках.
 */
export function AboutUniversity({
  university,
  description,
}: {
  university: University;
  description?: CampusDescription | null;
}) {
  const facts: { label: string; value: string }[] = [];
  if (university.inception) {
    facts.push({ label: "Основан", value: university.inception.slice(0, 4) });
  }
  if (university.students) {
    facts.push({ label: "Студентов", value: university.students.toLocaleString("ru-RU") });
  }
  if (university.staff) {
    facts.push({ label: "Сотрудников", value: university.staff.toLocaleString("ru-RU") });
  }
  if (university.city) {
    facts.push({
      label: "Город",
      value: [university.city, university.country].filter(Boolean).join(", "),
    });
  }
  if (university.short_name) {
    facts.push({ label: "Сокращение", value: university.short_name });
  }

  const spoken = description?.summary || university.description || "";
  const hasAnything = facts.length > 0 || university.description || description;
  if (!hasAnything) return null;

  return (
    <section className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-4 sm:p-5">
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-base font-semibold sm:text-lg">О вузе</h2>
        <a
          href={university.wikidata_url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-[var(--muted)] hover:underline"
        >
          факты из Wikidata · {university.id}
        </a>
      </header>

      {university.description && (
        <p className="mt-2 text-sm text-[var(--muted)]">{university.description}</p>
      )}

      {facts.length > 0 && (
        <dl className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-3">
          {facts.map((f) => (
            <div key={f.label} className="rounded-xl bg-[var(--surface-2)] px-3 py-2">
              <dt className="text-[11px] leading-tight text-[var(--muted)]">{f.label}</dt>
              <dd className="font-mono text-sm">{f.value}</dd>
            </div>
          ))}
        </dl>
      )}

      <div className="mt-3 flex flex-wrap gap-2">
        {university.website && (
          <a
            href={university.website}
            target="_blank"
            rel="noopener noreferrer"
            className="rounded-lg border border-[var(--border)] px-3 py-1.5 text-xs hover:border-[var(--accent)]"
          >
            Официальный сайт
          </a>
        )}
        {spoken && <SpeakButton text={spoken} />}
      </div>
    </section>
  );
}

/** Озвучка текста синтезом речи браузера. Ничего не скачивает и не генерирует. */
function SpeakButton({ text }: { text: string }) {
  const [speaking, setSpeaking] = useState(false);
  const [supported, setSupported] = useState(false);

  useEffect(() => {
    // Проверку откладываем на кадр: на сервере speechSynthesis нет, а ставить
    // состояние прямо в теле эффекта нельзя.
    const frame = window.requestAnimationFrame(() =>
      setSupported("speechSynthesis" in window),
    );
    return () => {
      window.cancelAnimationFrame(frame);
      // Уходим со страницы — голос не должен продолжать говорить.
      if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    };
  }, []);

  if (!supported) return null;

  const toggle = () => {
    if (speaking) {
      window.speechSynthesis.cancel();
      setSpeaking(false);
      return;
    }
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "ru-RU";
    utterance.rate = 1.05;
    utterance.onend = () => setSpeaking(false);
    utterance.onerror = () => setSpeaking(false);
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utterance);
    setSpeaking(true);
  };

  return (
    <button
      type="button"
      onClick={toggle}
      aria-pressed={speaking}
      className="rounded-lg border border-[var(--border)] px-3 py-1.5 text-xs hover:border-[var(--accent)]"
    >
      {speaking ? "Остановить" : "Слушать обзор"}
    </button>
  );
}
