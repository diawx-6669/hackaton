"use client";

import Link from "next/link";
import { useAuth } from "@/lib/auth";

/**
 * Пускает к содержимому только вошедшего пользователя.
 * Пока проверяем токен — показываем заглушку, иначе на долю секунды
 * мигает приглашение войти у уже вошедшего.
 */
export function AuthGate({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="mx-auto w-full max-w-md px-4 py-20 text-center text-sm text-[var(--muted)]">
        Проверяем вход…
      </div>
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
