import Link from "next/link";
import { Sparkle } from "./Icons";

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-40 border-b border-[var(--border-soft)] bg-[oklch(0.1_0.03_268_/_55%)] backdrop-blur-md">
      <nav className="mx-auto flex w-full max-w-6xl items-center justify-between gap-2 px-4 py-3 sm:gap-4 sm:px-6">
        <Link href="/" className="flex shrink-0 items-center gap-2.5">
          <span className="brand-mark grid size-8 place-items-center rounded-xl">
            <Sparkle className="h-4 w-4" />
          </span>
          <span className="font-display whitespace-nowrap text-base font-semibold sm:text-xl">
            CampusLens
          </span>
        </Link>
        <div className="flex items-center gap-0.5 text-xs sm:gap-1 sm:text-sm">
          <Link
            href="/"
            className="whitespace-nowrap rounded-lg px-1.5 py-1.5 text-[var(--muted)] hover:bg-[var(--surface)] hover:text-[var(--foreground)] sm:px-3"
          >
            Поиск
          </Link>
          <Link
            href="/compare"
            className="whitespace-nowrap rounded-lg px-1.5 py-1.5 text-[var(--muted)] hover:bg-[var(--surface)] hover:text-[var(--foreground)] sm:px-3"
          >
            {/* На узком экране «Сравнить вузы» ломало шапку на две строки */}
            <span className="sm:hidden">Сравнить</span>
            <span className="hidden sm:inline">Сравнить вузы</span>
          </Link>
          {/* На 375px ссылка распирала шапку, поэтому ниже 400px прячем: она есть в подвале */}
          <a
            href="https://github.com/diawx-6669/hackaton"
            target="_blank"
            rel="noopener noreferrer"
            className="hidden rounded-lg px-1.5 py-1.5 text-[var(--muted)] hover:bg-[var(--surface)] hover:text-[var(--foreground)] min-[400px]:block sm:px-3"
          >
            GitHub
          </a>
        </div>
      </nav>
    </header>
  );
}
