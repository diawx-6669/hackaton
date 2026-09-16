"use client";

import { useEffect } from "react";

/**
 * Фон из макета: снимок туманности, звёздная пыль и пятно подсветки,
 * которое следует за курсором. Сцена зафиксирована за контентом, поэтому
 * одинаково работает на всех страницах.
 *
 * Изображение декоративное и абстрактное — его нельзя принять за фото
 * кампуса, так что правило «никаких захардкоженных фотографий» не нарушено.
 */
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
      <img
        src="/cosmic-background.jpg"
        alt=""
        width={1920}
        height={1088}
        className="cosmic-image"
        fetchPriority="high"
      />
      <div className="star-field" />
      <div className="pointer-glow" />
      <div className="scene-shade" />
    </div>
  );
}
