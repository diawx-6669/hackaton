"use client";

import { useEffect } from "react";

/**
 * Живой фон: текучие ленты и мягкие пятна света, которые всё время движутся.
 *
 * Анимация сделана только на transform и opacity, то есть считается видеокартой
 * и не заставляет браузер пересчитывать вёрстку. Ни одного кадра на JavaScript:
 * страница в это же время принимает поток SSE, и отдавать ей на фон ещё и
 * requestAnimationFrame было бы расточительно.
 *
 * Фон полностью абстрактный — его нельзя принять за фотографию кампуса, так что
 * правило «никаких захардкоженных фотографий» не нарушено.
 */
const RIBBONS = [
  // d — форма ленты, duration — за сколько секунд проходит полный цикл.
  // Половина лент идёт вниз, половина вверх: пересекаясь, они дают объём,
  // иначе фон читается как просто полосатый.
  { d: "M-200 620 C 250 380, 620 780, 1020 480 S 1560 180, 2120 420", duration: 46, delay: 0, width: 150, opacity: 0.3 },
  { d: "M-200 760 C 300 520, 700 900, 1080 620 S 1600 320, 2120 560", duration: 62, delay: -8, width: 110, opacity: 0.24 },
  { d: "M-200 420 C 200 250, 640 560, 1060 300 S 1620 60, 2120 260", duration: 78, delay: -20, width: 90, opacity: 0.2 },
  { d: "M-200 900 C 320 700, 760 1020, 1140 760 S 1680 520, 2120 700", duration: 54, delay: -30, width: 130, opacity: 0.18 },
  // встречные
  { d: "M-200 300 C 340 640, 780 240, 1180 640 S 1700 900, 2120 640", duration: 68, delay: -14, width: 120, opacity: 0.22 },
  { d: "M-200 140 C 420 520, 820 120, 1260 520 S 1780 760, 2120 480", duration: 88, delay: -36, width: 70, opacity: 0.16 },
];

// Пузыри света. Значения подобраны так, чтобы они не выстраивались в сетку.
const ORBS = [
  { x: 86, y: 18, size: 190, duration: 34, delay: 0 },
  { x: 62, y: 72, size: 130, duration: 44, delay: -6 },
  { x: 48, y: 86, size: 80, duration: 38, delay: -14 },
  { x: 71, y: 78, size: 46, duration: 50, delay: -22 },
  { x: 17, y: 44, size: 34, duration: 42, delay: -9 },
  { x: 15, y: 52, size: 22, duration: 46, delay: -27 },
  { x: 93, y: 24, size: 52, duration: 40, delay: -17 },
];

export function CosmicScene() {
  useEffect(() => {
    // Подсветка за курсором — только для мыши: на тачскрине она бесполезна
    // и лишний раз дёргает перерисовку.
    const media = window.matchMedia("(pointer: fine)");
    if (!media.matches) return;

    let frame = 0;
    const move = (event: PointerEvent) => {
      if (frame) return;
      frame = requestAnimationFrame(() => {
        frame = 0;
        const root = document.documentElement;
        root.style.setProperty("--pointer-x", `${(event.clientX / window.innerWidth) * 100}%`);
        root.style.setProperty("--pointer-y", `${(event.clientY / window.innerHeight) * 100}%`);
      });
    };

    window.addEventListener("pointermove", move, { passive: true });
    return () => {
      window.removeEventListener("pointermove", move);
      if (frame) cancelAnimationFrame(frame);
    };
  }, []);

  return (
    <div className="cosmic-scene" aria-hidden="true">
      <div className="scene-base" />

      <svg className="ribbons" viewBox="0 0 1920 1080" preserveAspectRatio="xMidYMid slice">
        <defs>
          <linearGradient id="ribbon-line" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0" stopColor="oklch(0.62 0.09 225)" stopOpacity="0" />
            <stop offset="0.3" stopColor="oklch(0.78 0.11 220)" stopOpacity="0.85" />
            <stop offset="0.65" stopColor="oklch(0.7 0.13 245)" stopOpacity="0.7" />
            <stop offset="1" stopColor="oklch(0.6 0.1 250)" stopOpacity="0" />
          </linearGradient>
          {/* Размытие даёт шёлковую мягкость — без него это просто линии. */}
          <filter id="ribbon-blur" x="-20%" y="-40%" width="140%" height="180%">
            <feGaussianBlur stdDeviation="14" />
          </filter>
        </defs>

        {RIBBONS.map((r, i) => (
          <g
            key={i}
            className="ribbon"
            style={{ animationDuration: `${r.duration}s`, animationDelay: `${r.delay}s` }}
          >
            <path
              d={r.d}
              fill="none"
              stroke="url(#ribbon-line)"
              strokeWidth={r.width}
              strokeLinecap="round"
              opacity={r.opacity}
              filter="url(#ribbon-blur)"
            />
            <path
              d={r.d}
              fill="none"
              stroke="url(#ribbon-line)"
              strokeWidth={Math.round(r.width / 6)}
              strokeLinecap="round"
              opacity={r.opacity * 1.6}
            />
          </g>
        ))}
      </svg>

      <div className="orbs">
        {ORBS.map((o, i) => (
          <span
            key={i}
            className="orb"
            style={{
              left: `${o.x}%`,
              top: `${o.y}%`,
              width: o.size,
              height: o.size,
              animationDuration: `${o.duration}s`,
              animationDelay: `${o.delay}s`,
            }}
          />
        ))}
      </div>

      <div className="pointer-glow" />
      <div className="scene-shade" />
    </div>
  );
}
