"use client";

import type { CampusVideo, EventGroup, Photo } from "@/lib/types";

/**
 * События и видео.
 *
 * Календаря мероприятий тут нет и быть не может: расписания вуза мы не знаем.
 * Есть другое — фотографии, которые уже прошли проверку и по метаданным
 * похожи на съёмку с события, разложенные по годам. Это утверждение о том,
 * что сняли и выложили, а не о том, что вуз проводит.
 *
 * Видео — только с Wikimedia Commons. TikTok, VK и Shorts мы не трогаем:
 * их правила и robots.txt это запрещают, а ТЗ требует их соблюдать.
 */
export function EventsBlock({
  events,
  videos,
  photos,
  onOpen,
}: {
  events: EventGroup[];
  videos: CampusVideo[];
  photos: Photo[];
  onOpen: (photo: Photo) => void;
}) {
  if (events.length === 0 && videos.length === 0) return null;
  const byId = new Map(photos.map((p) => [p.id, p]));

  return (
    <section className="grid gap-4">
      {events.length > 0 && (
        <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-4 sm:p-5">
          <header className="flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="text-base font-semibold sm:text-lg">События</h2>
            <span className="text-xs text-[var(--muted)]">
              по метаданным найденных фото, не по расписанию вуза
            </span>
          </header>

          <div className="mt-3 grid gap-3">
            {events.map((group) => {
              const items = group.photo_ids
                .map((id) => byId.get(id))
                .filter((p): p is Photo => Boolean(p));
              return (
                <div key={group.title}>
                  <div className="flex flex-wrap items-baseline gap-2">
                    <h3 className="text-sm font-medium">{group.title}</h3>
                    <span className="font-mono text-xs text-[var(--accent)]">
                      {group.count}
                    </span>
                    {group.years.length > 0 && (
                      <span className="text-xs text-[var(--muted)]">
                        {group.years.join(", ")}
                      </span>
                    )}
                  </div>
                  {items.length > 0 && (
                    <div className="mt-1.5 flex gap-2 overflow-x-auto pb-1">
                      {items.slice(0, 8).map((p) => (
                        <button
                          key={p.id}
                          onClick={() => onOpen(p)}
                          className="h-20 w-28 shrink-0 overflow-hidden rounded-lg border border-[var(--border)]"
                          title={p.title}
                        >
                          <img
                            src={p.thumb_url || p.url}
                            alt={p.title}
                            loading="lazy"
                            className="h-full w-full object-cover"
                          />
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {videos.length > 0 && (
        <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-4 sm:p-5">
          <header className="flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="text-base font-semibold sm:text-lg">Видео</h2>
            <span className="text-xs text-[var(--muted)]">Wikimedia Commons</span>
          </header>

          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            {videos.map((v) => (
              <figure key={v.id} className="overflow-hidden rounded-xl bg-[var(--surface-2)]">
                <video
                  src={v.url}
                  controls
                  preload="metadata"
                  className="aspect-video w-full bg-black"
                />
                <figcaption className="grid gap-1 p-2 text-xs">
                  <a
                    href={v.source_page_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="line-clamp-2 hover:underline"
                  >
                    {v.title}
                  </a>
                  <span className="text-[var(--muted)]">
                    {v.author || "автор не указан"} · {v.license || "лицензия не указана"}
                    {v.duration_s ? ` · ${v.duration_s} с` : ""}
                  </span>
                </figcaption>
              </figure>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
