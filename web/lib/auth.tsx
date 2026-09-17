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
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, name: string) => Promise<void>;
  logout: () => void;
};

const Ctx = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  // Восстанавливаем сессию по сохранённому токену.
  useEffect(() => {
    let cancelled = false;

    void (async () => {
      const token = readToken();
      if (!token) {
        if (!cancelled) setLoading(false);
        return;
      }
      try {
        const res = await fetch(`${API_BASE}/api/auth/me`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (cancelled) return;
        if (res.ok) setUser(await res.json());
        else writeToken(null); // токен протух или подписан другим секретом
      } catch {
        // Бэкенд недоступен — выходить из аккаунта не за что.
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
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
      login: (email, password) => submit("login", { email, password }),
      register: (email, password, name) => submit("register", { email, password, name }),
      logout: () => {
        writeToken(null);
        setUser(null);
      },
    }),
    [user, loading, submit],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useAuth вызван вне AuthProvider");
  return ctx;
}
