"use client";

import { useEffect, useState } from "react";

export type NavSection = { id: string; label: string };

/**
 * Панель разделов профиля: липнет под шапкой сайта и ведёт к блокам.
 *
 * Профиль вырос до восьми блоков, и без неё до «Сколько добираться» нужно
 * прокрутить полэкрана. В панель попадают только те разделы, которые реально
 * собрались: пустых пунктов, ведущих в никуда, здесь нет.
 */
export function ProfileNav({ sections }: { sections: NavSection[] }) {
  const [active, setActive] = useState<string | null>(null);

  useEffect(() => {
    if (sections.length === 0) return;
    const nodes = sections
      .map((s) => document.getElementById(s.id))
      .filter((n): n is HTMLElement => Boolean(n));

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
        if (visible) setActive(visible.target.id);
      },
      // Верхняя граница опущена на высоту двух панелей, иначе активным
      // считался бы раздел, который уже уехал под шапку.
      { rootMargin: "-120px 0px -65% 0px", threshold: 0 },
    );
    nodes.forEach((n) => observer.observe(n));
    return () => observer.disconnect();
  }, [sections]);

  if (sections.length === 0) return null;

  // min-w-0 обязателен: панель — прямой потомок грида, а у элемента грида
  // min-width по умолчанию auto, и прокручиваемый список внутри растягивал
  // всю колонку профиля шире экрана. На телефоне это давало горизонтальную
  // прокрутку всей страницы — ловится mobile.spec.ts.
  return (
    <nav
      aria-label="Разделы профиля"
      className="sticky top-[57px] z-30 min-w-0 rounded-xl border border-[var(--border-soft)] bg-[oklch(0.1_0.03_268_/_82%)] px-2 backdrop-blur-md"
    >
      <ul className="flex gap-1 overflow-x-auto py-2">
        {sections.map((s) => (
          <li key={s.id}>
            <a
              href={`#${s.id}`}
              aria-current={active === s.id ? "true" : undefined}
              onClick={(e) => {
                e.preventDefault();
                const node = document.getElementById(s.id);
                if (!node) return;
                // scrollIntoView увёл бы заголовок под две липкие панели.
                const top = node.getBoundingClientRect().top + window.scrollY - 110;
                window.scrollTo({ top, behavior: "smooth" });
                setActive(s.id);
              }}
              className={`block whitespace-nowrap rounded-lg px-3 py-1.5 text-xs transition sm:text-sm ${
                active === s.id
                  ? "bg-[var(--surface-2)] text-[var(--foreground)]"
                  : "text-[var(--muted)] hover:text-[var(--foreground)]"
              }`}
            >
              {s.label}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  );
}
