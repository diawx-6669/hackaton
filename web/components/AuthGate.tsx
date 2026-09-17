"use client";

import Link from "next/link";
import { useAuth } from "@/lib/auth";

/**
 * Пускает к содержимому только вошедшего пользователя.
 *
 * Три разных состояния, которые нельзя путать: проверяем токен, сервер
 * не ответил, пользователь не вошёл. Раньше первое висело без конца, пока
 * просыпался контейнер Render, а третье показывалось вместо второго —
 * вошедший человек читал «нужен вход» и думал, что его разлогинило.
 */
export function AuthGate({ children }: { children: React.ReactNode }) {
  const { user, loading, slow, authError, retry } = useAuth();

  if (loading) {
    return (
      <div className="mx-auto w-full max-w-md px-4 py-20 text-center text-sm text-[var(--muted)]">
        Проверяем вход…
        {slow && (
          <p className="mt-2 text-xs">
            Бесплатный сервер просыпается после простоя — это занимает до минуты.
          </p>
        )}
      </div>
    );
  }

  if (authError && !user) {
    return (
      <section className="mx-auto w-full max-w-md px-4 py-16">
        <div className="card p-6 text-center">
          <h2 className="font-display text-xl font-semibold">Сервер недоступен</h2>
          <p className="mt-2 text-sm text-[var(--muted)]">
            Не удалось связаться с API, поэтому неизвестно, вошли вы или нет.
            Это не ошибка входа.
          </p>
          <p className="mt-2 font-mono text-xs break-all text-[var(--muted)]">{authError}</p>
          <div className="mt-5 flex flex-wrap justify-center gap-2">
            <button
              type="button"
              onClick={retry}
              className="primary-action rounded-lg px-5 py-2.5 font-semibold"
            >
              Повторить
            </button>
            <Link
              href="/login"
              className="rounded-lg border border-[var(--border)] px-5 py-2.5 font-medium text-[var(--muted)] hover:text-[var(--foreground)]"
            >
              Войти заново
            </Link>
          </div>
        </div>
      </section>
    );
  }

  if (!user) {
    return (
      <section className="mx-auto w-full max-w-md px-4 py-16">
        <div className="card p-6 text-center">
          <h2 className="font-display text-xl font-semibold">Нужен вход</h2>
          <p className="mt-2 text-sm text-[var(--muted)]">
            Профили вузов доступны после входа в аккаунт.
          </p>
          <Link
            href="/login"
            className="primary-action mt-5 inline-block rounded-lg px-6 py-2.5 font-semibold"
          >
            Войти или зарегистрироваться
          </Link>
        </div>
      </section>
    );
  }

  return <>{children}</>;
}
