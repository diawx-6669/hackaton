"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { API_BASE } from "./api";

export type User = { id: string; email: string; name: string };

const TOKEN_KEY = "campuslens-token";

function readToken(): string | null {
  try {
    return window.localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

function writeToken(token: string | null) {
  try {
    if (token) window.localStorage.setItem(TOKEN_KEY, token);
    else window.localStorage.removeItem(TOKEN_KEY);
  } catch {
    // Приватный режим — сессия проживёт до перезагрузки страницы.
  }
}

/** Заголовок для запросов, которым нужен вошедший пользователь. */
export function authHeaders(): HeadersInit {
  const token = typeof window === "undefined" ? null : readToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

type AuthState = {
  user: User | null;
  loading: boolean;
  /** Проверка идёт дольше пары секунд — обычно это просыпается бесплатный Render. */
  slow: boolean;
  /** Бэкенд не ответил. Это не «вы не вошли», и говорить так нельзя. */
  authError: string | null;
  retry: () => void;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, name: string) => Promise<void>;
  logout: () => void;
};

// Контейнер на бесплатном тарифе Render просыпается 30–60 с. Ждём до 70,
// потом честно говорим, что сервер не отвечает, вместо вечного «Проверяем вход…».
const ME_TIMEOUT_MS = 70_000;
const SLOW_AFTER_MS = 2_500;

const Ctx = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [slow, setSlow] = useState(false);
  const [authError, setAuthError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  // Восстанавливаем сессию по сохранённому токену.
  useEffect(() => {
    let cancelled = false;
    const controller = new AbortController();
    const slowTimer = setTimeout(() => {
      if (!cancelled) setSlow(true);
    }, SLOW_AFTER_MS);
    const hardTimer = setTimeout(() => controller.abort(), ME_TIMEOUT_MS);

    void (async () => {
      const token = readToken();
      if (!token) {
        if (!cancelled) setLoading(false);
        return;
      }
      try {
        const res = await fetch(`${API_BASE}/api/auth/me`, {
          headers: { Authorization: `Bearer ${token}` },
          signal: controller.signal,
        });
        if (cancelled) return;
        if (res.ok) {
          setUser(await res.json());
          setAuthError(null);
        } else if (res.status === 401) {
          writeToken(null); // токен протух или подписан другим секретом
          setAuthError(null);
        } else {
          setAuthError(`Сервер ответил ${res.status}`);
        }
      } catch {
        // Токен не трогаем: бэкенд мог просто спать. Но и молчать нельзя —
        // иначе вошедший пользователь увидит «нужен вход» и решит, что его
        // выкинуло.
        if (!cancelled) setAuthError(`Сервер не отвечает (${API_BASE})`);
      } finally {
        clearTimeout(slowTimer);
        clearTimeout(hardTimer);
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
      clearTimeout(slowTimer);
      clearTimeout(hardTimer);
      controller.abort();
    };
  }, [attempt]);

  const retry = useCallback(() => {
    setAuthError(null);
    setSlow(false);
    setLoading(true);
    setAttempt((n) => n + 1);
  }, []);

  const submit = useCallback(
    async (path: string, body: Record<string, string>) => {
      const res = await fetch(`${API_BASE}/api/auth/${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        throw new Error(
          typeof data?.detail === "string" ? data.detail : "Не удалось выполнить вход",
        );
      }
      writeToken(data.token);
      setUser(data.user);
    },
    [],
  );

  const value = useMemo<AuthState>(
    () => ({
      user,
      loading,
      slow,
      authError,
      retry,
      login: (email, password) => submit("login", { email, password }),
      register: (email, password, name) => submit("register", { email, password, name }),
      logout: () => {
        writeToken(null);
        setUser(null);
      },
    }),
    [user, loading, slow, authError, retry, submit],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useAuth вызван вне AuthProvider");
  return ctx;
}
