"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const { user, login, register } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (mode === "login") await login(email.trim(), password);
      else await register(email.trim(), password, name.trim());
      router.push("/my");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (user) {
    return (
      <main className="mx-auto w-full max-w-md px-4 py-16">
        <section className="card p-6 text-center">
          <h1 className="font-display text-xl font-semibold">Вы уже вошли</h1>
          <p className="mt-2 text-sm text-[var(--muted)]">{user.email}</p>
          <Link
            href="/my"
            className="primary-action mt-5 inline-block rounded-lg px-5 py-2.5 font-semibold"
          >
            Мои фото
          </Link>
        </section>
      </main>
    );
  }

  return (
    <main className="mx-auto w-full max-w-md px-4 py-10 sm:py-16">
      <section className="glass-panel rounded-2xl p-5 sm:p-7">
        <div className="tab-shell grid grid-cols-2 rounded-full p-1">
          <button
            type="button"
            onClick={() => setMode("login")}
            className={`tab-button rounded-full ${mode === "login" ? "tab-active" : ""}`}
          >
            Вход
          </button>
          <button
            type="button"
            onClick={() => setMode("register")}
            className={`tab-button rounded-full ${mode === "register" ? "tab-active" : ""}`}
          >
            Регистрация
          </button>
        </div>

        <form onSubmit={submit} className="mt-6 grid gap-3">
          <h1 className="font-display text-2xl font-semibold">
            {mode === "login" ? "С возвращением" : "Создать аккаунт"}
          </h1>
          <p className="text-xs text-[var(--muted)]">
            Аккаунт нужен, чтобы ваши фотографии и бонусы были доступны с любого устройства.
          </p>

          {mode === "register" && (
            <label className="grid gap-1 text-xs font-medium">
              Имя
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                maxLength={60}
                placeholder="Как вас зовут"
                className="field h-11 rounded-lg bg-transparent px-3 text-sm font-normal outline-none placeholder:text-[var(--muted)]"
              />
            </label>
          )}

          <label className="grid gap-1 text-xs font-medium">
            Почта
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              placeholder="you@example.com"
              className="field h-11 rounded-lg bg-transparent px-3 text-sm font-normal outline-none placeholder:text-[var(--muted)]"
            />
          </label>

          <label className="grid gap-1 text-xs font-medium">
            Пароль
            <input
              type="password"
              required
              minLength={mode === "register" ? 8 : 1}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              placeholder={mode === "register" ? "минимум 8 символов" : "••••••••"}
              className="field h-11 rounded-lg bg-transparent px-3 text-sm font-normal outline-none placeholder:text-[var(--muted)]"
            />
          </label>

          {error && <p className="text-sm text-[var(--bad)]">{error}</p>}

          <button
            type="submit"
            disabled={busy || !email.trim() || password.length < 1}
            className="primary-action mt-2 h-11 rounded-lg font-semibold"
          >
            {busy ? "Отправляем…" : mode === "login" ? "Войти" : "Зарегистрироваться"}
          </button>

          <p className="text-[11px] leading-4 text-[var(--muted)]">
            Пароль хранится только в виде хеша. Подтверждения почты пока нет,
            а на бесплатном хостинге диск эфемерный — после передеплоя сервиса
            аккаунты придётся создавать заново. Это учебный проект, не храните
            здесь важный пароль.
          </p>
        </form>
      </section>

      <p className="mt-4 text-center text-xs text-[var(--muted)]">
        Можно и без аккаунта:{" "}
        <Link href="/my" className="text-[var(--accent)] underline">
          загрузить фото анонимно
        </Link>
      </p>
    </main>
  );
}
