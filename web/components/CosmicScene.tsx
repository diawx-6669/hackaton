"use client";

import { useEffect } from "react";

/**
 * Живой фон: шёлковые ленты и пятна света.
 *
 * Формы, цвета и тайминги перенесены из присланного макета
 * (CosmicBackground.tsx + styles.css) без изменений — это его фон, а не мой
 * пересказ. Здесь он разложен на переменные, чтобы править числа в одном месте.
 *
 * Анимация только на transform и opacity: считает видеокарта, вёрстка не
 * пересчитывается. Ни одного кадра на JavaScript — страница в это же время
 * принимает поток SSE и дорисовывает галерею.
 *
 * Фон полностью абстрактный, его нельзя принять за фотографию кампуса, так что
 * правило «никаких захардкоженных фотографий» не нарушено.
 */
const RIBBONS = [
  "M-180 670 C 230 390 590 780 1010 500 S 1570 170 2110 410",
  "M-180 790 C 270 530 690 900 1080 630 S 1610 300 2110 550",
  "M-180 430 C 250 210 650 570 1060 310 S 1630 70 2110 250",
  "M-180 250 C 360 610 780 220 1190 620 S 1720 900 2110 650",
];

const ORBS = ["orb-one", "orb-two", "orb-three", "orb-four", "orb-five"];

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
          <linearGradient id="ribbon-color" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0" stopColor="var(--ribbon-start)" stopOpacity="0" />
            <stop offset="0.32" stopColor="var(--ribbon-bright)" stopOpacity="0.82" />
            <stop offset="0.68" stopColor="var(--ribbon-mid)" stopOpacity="0.68" />
            <stop offset="1" stopColor="var(--ribbon-end)" stopOpacity="0" />
          </linearGradient>
          {/* Широкая размытая лента плюс тонкая чёткая поверх — отсюда шёлк. */}
          <filter id="ribbon-blur" x="-20%" y="-50%" width="140%" height="200%">
            <feGaussianBlur stdDeviation="17" />
          </filter>
        </defs>

        {RIBBONS.map((path, index) => (
          <g key={path} className={`ribbon ribbon-${index + 1}`}>
            <path
              d={path}
              fill="none"
              stroke="url(#ribbon-color)"
              strokeWidth="130"
              strokeLinecap="round"
              filter="url(#ribbon-blur)"
            />
            <path
              d={path}
              fill="none"
              stroke="url(#ribbon-color)"
              strokeWidth="20"
              strokeLinecap="round"
            />
          </g>
        ))}
      </svg>

      <div className="orbs">
        {ORBS.map((orb) => (
          <span key={orb} className={`orb ${orb}`} />
        ))}
      </div>

      <div className="pointer-glow" />
      <div className="scene-shade" />
    </div>
  );
}
