"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { myUploads, myWallet, uploadPhoto, uploadUrl } from "@/lib/api";
import { AuthGate } from "@/components/AuthGate";
import { useAuth } from "@/lib/auth";
import type { UploadRecord, Wallet } from "@/lib/types";

export default function MyPhotosPage() {
  const { user } = useAuth();
  const [items, setItems] = useState<UploadRecord[]>([]);
  const [wallet, setWallet] = useState<Wallet | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [caption, setCaption] = useState("");
  const [university, setUniversity] = useState("");
  const cameraRef = useRef<HTMLInputElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  // Обновление после загрузки фото — вызывается из обработчика, не из эффекта.
  const refresh = useCallback(async () => {
    try {
      const [list, balance] = await Promise.all([myUploads(), myWallet()]);
      setItems(list);
      setWallet(balance);
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  // Первая загрузка: с флагом отмены, чтобы не трогать состояние
  // размонтированной страницы, если пользователь ушёл раньше ответа.
  useEffect(() => {
    let cancelled = false;

    void (async () => {
      try {
        const [list, balance] = await Promise.all([myUploads(), myWallet()]);
        if (cancelled) return;
        setItems(list);
        setWallet(balance);
      } catch (e) {
        if (!cancelled) setError((e as Error).message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  async function handleFile(file: File | undefined) {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      await uploadPhoto(file, { universityName: university.trim(), caption: caption.trim() });
      setCaption("");
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
      if (cameraRef.current) cameraRef.current.value = "";
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  return (
    <main className="mx-auto flex w-full max-w-5xl flex-col gap-5 px-4 py-8 sm:px-6 sm:py-10">
      <AuthGate>
      <header>
        <h1 className="font-display text-2xl font-semibold sm:text-3xl">Мои фото</h1>
        <p className="mt-2 max-w-2xl text-sm leading-relaxed text-[var(--muted)]">
          Учишься здесь? Сфотографируй место и загрузи — за каждый принятый снимок
          начисляются бонусы.
        </p>
        {user && (
          <p className="mt-2 text-xs text-[var(--muted)]">{user.email}</p>
        )}
      </header>

      {/* Кошелёк */}
      <section className="card grid grid-cols-3 gap-2 p-4">
        <div>
          <p className="text-xs text-[var(--muted)]">бонусов</p>
          <p className="font-mono text-2xl text-[var(--accent)]">{wallet?.coins ?? 0}</p>
        </div>
        <div>
          <p className="text-xs text-[var(--muted)]">фотографий</p>
          <p className="font-mono text-2xl">{wallet?.photos ?? 0}</p>
        </div>
        <div>
          <p className="text-xs text-[var(--muted)]">за снимок</p>
          <p className="font-mono text-2xl">+{wallet?.per_photo ?? 10}</p>
        </div>
      </section>

      {/* Загрузка */}
      <section className="card grid gap-3 p-4">
        <div className="grid gap-2 sm:grid-cols-2">
          <input
            value={university}
            onChange={(e) => setUniversity(e.target.value)}
            placeholder="Какой вуз? Например, КБТУ"
            className="field h-11 rounded-lg bg-transparent px-3 text-sm outline-none placeholder:text-[var(--muted)]"
          />
          <input
            value={caption}
            onChange={(e) => setCaption(e.target.value)}
            placeholder="Что на фото? Например, библиотека"
            maxLength={200}
            className="field h-11 rounded-lg bg-transparent px-3 text-sm outline-none placeholder:text-[var(--muted)]"
          />
        </div>

        <div className="grid gap-2 sm:grid-cols-2">
          {/* capture открывает камеру на телефоне, на десктопе — обычный выбор файла */}
          <input
            ref={cameraRef}
            type="file"
            accept="image/*"
            capture="environment"
            className="hidden"
            onChange={(e) => handleFile(e.target.files?.[0])}
          />
          <input
            ref={fileRef}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            className="hidden"
            onChange={(e) => handleFile(e.target.files?.[0])}
          />
          <button
            type="button"
            disabled={busy}
            onClick={() => cameraRef.current?.click()}
            className="primary-action h-11 rounded-lg font-semibold"
          >
            {busy ? "Загружаем…" : "Сфотографировать"}
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() => fileRef.current?.click()}
            className="h-11 rounded-lg border border-[var(--border)] font-medium text-[var(--muted)] transition hover:text-[var(--foreground)] disabled:opacity-40"
          >
            Выбрать из галереи
          </button>
        </div>

        {error && <p className="text-sm text-[var(--bad)]">{error}</p>}

        <p className="text-[11px] leading-4 text-[var(--muted)]">
          JPEG, PNG или WebP до 8 МБ. EXIF удаляется при сохранении.
        </p>
      </section>

      {/* Галерея */}
      <section className="grid gap-3">
        <h2 className="font-display text-lg font-semibold">Загруженное</h2>

        {loading ? (
          <p className="text-sm text-[var(--muted)]">Загружаем…</p>
        ) : items.length === 0 ? (
          <p className="card p-6 text-center text-sm text-[var(--muted)]">
            Пока пусто. Первое фото принесёт {wallet?.per_photo ?? 10} бонусов.
          </p>
        ) : (
          <div className="grid grid-cols-2 gap-2 sm:gap-3 lg:grid-cols-4">
            {items.map((item) => (
              <figure key={item.id} className="card overflow-hidden">
                <img
                  src={uploadUrl(item.url)}
                  alt={item.caption ?? "Загруженное фото"}
                  loading="lazy"
                  className="aspect-[4/3] w-full object-cover"
                />
                <figcaption className="grid gap-1 p-2 text-[11px] sm:text-xs">
                  {item.caption && <span className="line-clamp-2">{item.caption}</span>}
                  {item.university_name && (
                    <span className="text-[var(--muted)]">{item.university_name}</span>
                  )}
                  <span className="flex items-center justify-between text-[var(--muted)]">
                    <span>+{item.coins}</span>
                    {item.has_geotag && <span title="В файле была геометка">📍</span>}
                  </span>
                </figcaption>
              </figure>
            ))}
          </div>
        )}
      </section>

      <footer className="card p-4 text-xs leading-5 text-[var(--muted)]">
        <b className="text-[var(--foreground)]">Эти снимки не попадают в проверенную галерею.</b>{" "}
        У фото из открытого источника есть автор, лицензия и ссылка — у загруженного нет.
        Поэтому оно живёт отдельно и не влияет на достоверность профиля вуза.
      </footer>
      </AuthGate>
    </main>
  );
}
