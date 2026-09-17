"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";
import Image from "next/image";

const MENU = [
  { href: "/", label: "Поиск" },
  { href: "/compare", label: "Сравнить вузы" },
  { href: "/my", label: "Мои фото" },
];

export function SiteHeader() {
  const pathname = usePathname();
  const { user, loading, logout } = useAuth();
  const [open, setOpen] = useState(false);

  const link = (href: string, label: string) => (
    <Link
      key={href}
      href={href}
      // Закрываем меню прямо здесь: реагировать эффектом на смену пути
      // значит лишний раз перерисовывать шапку после каждого перехода.
      onClick={() => setOpen(false)}
      className={`whitespace-nowrap rounded-lg px-3 py-2 transition hover:bg-[var(--surface)] hover:text-[var(--foreground)] ${
        pathname === href ? "text-[var(--foreground)]" : "text-[var(--muted)]"
      }`}
    >
      {label}
    </Link>
  );

  return (
    <header className="sticky top-0 z-40 border-b border-[var(--border-soft)] bg-[oklch(0.1_0.03_268_/_55%)] backdrop-blur-md">
      <nav className="mx-auto flex w-full max-w-6xl items-center justify-between gap-2 px-4 py-3 sm:gap-4 sm:px-6">
        <Link href="/" className="flex shrink-0 items-center gap-2.5">
          <Image
            src="/logo.svg"
            alt=""
            width={36}
            height={36}
            priority
            className="size-9 shrink-0"
          />
          <span className="font-display whitespace-nowrap text-base font-semibold sm:text-xl">
            CampusLens
          </span>
        </Link>

        {/* Полное меню — от планшета и шире */}
        <div className="hidden items-center gap-1 text-sm md:flex">
          {MENU.map((m) => link(m.href, m.label))}

          {loading ? null : user ? (
            <span className="ml-2 flex items-center gap-2 border-l border-[var(--border-soft)] pl-3">
              <span className="max-w-[10rem] truncate text-sm" title={user.email}>
                {user.name}
              </span>
              <button
                type="button"
                onClick={logout}
                className="rounded-lg px-2 py-1.5 text-xs text-[var(--muted)] transition hover:text-[var(--foreground)]"
              >
                Выйти
              </button>
            </span>
          ) : (
            <Link
              href="/login"
              className="ml-2 rounded-lg border border-[var(--border)] px-3 py-1.5 text-sm transition hover:border-[var(--accent)]"
            >
              Войти
            </Link>
          )}
        </div>

        {/* Кнопка меню — на телефоне */}
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          aria-label="Меню"
          className="grid size-9 shrink-0 place-items-center rounded-lg border border-[var(--border)] md:hidden"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-5 w-5">
            {open ? (
              <path d="m6 6 12 12M18 6 6 18" strokeLinecap="round" />
            ) : (
              <path d="M4 7h16M4 12h16M4 17h16" strokeLinecap="round" />
            )}
          </svg>
        </button>
      </nav>

      {open && (
        <div className="border-t border-[var(--border-soft)] bg-[oklch(0.1_0.03_268_/_92%)] px-4 py-2 md:hidden">
          <div className="mx-auto grid max-w-6xl gap-1 text-sm">
            {MENU.map((m) => link(m.href, m.label))}

            {loading ? null : user ? (
              <div className="mt-1 flex items-center justify-between border-t border-[var(--border-soft)] pt-2">
                <span className="truncate px-3 text-sm text-[var(--muted)]">{user.email}</span>
                <button
                  type="button"
                  onClick={logout}
                  className="rounded-lg px-3 py-2 text-sm text-[var(--muted)]"
                >
                  Выйти
                </button>
              </div>
            ) : (
              <Link
                href="/login"
                onClick={() => setOpen(false)}
                className="mt-1 rounded-lg border border-[var(--border)] px-3 py-2 text-center"
              >
                Войти
              </Link>
            )}

            <a
              href="https://github.com/diawx-6669/hackaton"
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-lg px-3 py-2 text-[var(--muted)]"
            >
              GitHub
            </a>
          </div>
        </div>
      )}
    </header>
  );
}
