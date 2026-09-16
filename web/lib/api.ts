import type { ResolveResponse, StageEvent } from "./types";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") || "http://localhost:8000";

export async function resolveUniversity(
  q: string,
  signal?: AbortSignal,
): Promise<ResolveResponse> {
  const res = await fetch(`${API_BASE}/api/resolve?q=${encodeURIComponent(q)}`, { signal });
  if (!res.ok) {
    throw new Error(`Поиск не удался (${res.status})`);
  }
  return res.json();
}

/**
 * Читает SSE-поток /api/profile вручную (fetch + ReadableStream), а не через
 * EventSource: так можно отменить запрос по AbortSignal и показать сетевую ошибку.
 */
export async function streamProfile(
  params: { q?: string; id?: string },
  onEvent: (event: StageEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const query = new URLSearchParams();
  if (params.id) query.set("id", params.id);
  else if (params.q) query.set("q", params.q);

  const res = await fetch(`${API_BASE}/api/profile?${query.toString()}`, {
    signal,
    headers: { Accept: "text/event-stream" },
  });
  if (!res.ok || !res.body) {
    throw new Error(`Стрим недоступен (${res.status})`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // События разделены пустой строкой; поле data: может быть многострочным.
    let sep: number;
    while ((sep = buffer.indexOf("\n\n")) !== -1) {
      const chunk = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      const data = chunk
        .split("\n")
        .filter((line) => line.startsWith("data:"))
        .map((line) => line.slice(5).trim())
        .join("");
      if (!data) continue; // ping-комментарии пропускаем
      try {
        onEvent(JSON.parse(data) as StageEvent);
      } catch {
        // Неполный или служебный кадр — игнорируем, поток продолжается.
      }
    }
  }
}
