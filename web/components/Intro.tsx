"use client";

import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Интро при первом заходе.
 *
 * Правила, из которых собрана эта штука:
 * — показывается один раз на браузер (флаг в localStorage), иначе она бесит;
 * — пропускается по кнопке, Esc и клику мимо — жюри не должно ждать ролик;
 * — при prefers-reduced-motion не запускается вовсе;
 * — если видео не поддерживается или не загрузилось, интро закрывается само,
 *   а не висит чёрным экраном;
 * — video грузится только когда интро реально показываем, поэтому на скорость
 *   первой отрисовки для вернувшегося пользователя не влияет.
 */
const SEEN_KEY = "campuslens-intro-seen";

export function Intro() {
  const [show, setShow] = useState(false);
  const [leaving, setLeaving] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    // Решение принимаем кадром позже: localStorage на сервере нет, а ставить
    // состояние прямо в теле эффекта нельзя — будет лишний проход рендера.
    const frame = window.requestAnimationFrame(() => {
      let seen = true;
      try {
        seen = window.localStorage.getItem(SEEN_KEY) === "1";
      } catch {
        // Приватный режим: считаем, что видели, — лучше не показать, чем навязать.
      }
      const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      if (!seen && !reduced) setShow(true);
    });
    return () => window.cancelAnimationFrame(frame);
  }, []);

  const close = useCallback(() => {
    try {
      window.localStorage.setItem(SEEN_KEY, "1");
    } catch {
      // Не смогли запомнить — не беда, интро просто покажется ещё раз.
    }
    setLeaving(true);
    window.setTimeout(() => setShow(false), 420);
  }, []);

  useEffect(() => {
    if (!show) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" || e.key === " " || e.key === "Enter") close();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [show, close]);

  if (!show) return null;

  return (
    <div
      role="dialog"
      aria-label="Заставка CampusLens"
      onClick={close}
      className={`fixed inset-0 z-[100] grid place-items-center bg-[#05080f] transition-opacity duration-400 ${
        leaving ? "opacity-0" : "opacity-100"
      }`}
    >
      <video
        ref={videoRef}
        src="/intro.mp4"
        autoPlay
        muted
        playsInline
        preload="auto"
        onEnded={close}
        onError={close}
        className="max-h-full max-w-full object-contain"
      />

      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          close();
        }}
        className="absolute bottom-6 right-6 rounded-lg border border-white/25 bg-black/40 px-4 py-2 text-sm text-white/80 backdrop-blur transition hover:text-white"
      >
        Пропустить
      </button>
    </div>
  );
}
