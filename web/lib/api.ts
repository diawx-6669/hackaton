import { getDeviceId } from "./device";
import type { Comparison, ResolveResponse, StageEvent, UploadRecord, Wallet } from "./types";

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
    // Спека SSE разрешает и \n, и \r\n; sse-starlette шлёт именно \r\n.
    // Нормализуем переводы строк, иначе разделитель событий не находится
    // и поток «приходит», но UI не обновляется никогда.
    buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");

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

export async function compareUniversities(
  a: string,
  b: string,
  signal?: AbortSignal,
): Promise<Comparison> {
  const params = new URLSearchParams({ a, b });
  const res = await fetch(`${API_BASE}/api/compare?${params}`, { signal });
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail ?? `Сравнение не удалось (${res.status})`);
  }
  return res.json();
}

/** Загрузки и кошелёк опознают пользователя по идентификатору устройства. */
function deviceHeaders(): HeadersInit {
  return { "X-Device-Id": getDeviceId() };
}

export async function uploadPhoto(
  file: File,
  extra: { universityName?: string; caption?: string } = {},
): Promise<UploadRecord> {
  const form = new FormData();
  form.append("file", file);
  if (extra.universityName) form.append("university_name", extra.universityName);
  if (extra.caption) form.append("caption", extra.caption);

  const res = await fetch(`${API_BASE}/api/uploads`, {
    method: "POST",
    headers: deviceHeaders(),
    body: form,
  });
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    throw new Error(typeof body?.detail === "string" ? body.detail : "Не удалось загрузить фото");
  }
  return body as UploadRecord;
}

export async function myUploads(): Promise<UploadRecord[]> {
  const res = await fetch(`${API_BASE}/api/uploads`, { headers: deviceHeaders() });
  if (!res.ok) throw new Error("Не удалось получить список фото");
  return (await res.json()).items as UploadRecord[];
}

export async function myWallet(): Promise<Wallet> {
  const res = await fetch(`${API_BASE}/api/wallet`, { headers: deviceHeaders() });
  if (!res.ok) throw new Error("Не удалось получить баланс");
  return res.json();
}

/** Файлы отдаёт бэкенд, поэтому относительный путь надо дополнить его адресом. */
export function uploadUrl(path: string): string {
  return path.startsWith("http") ? path : `${API_BASE}${path}`;
}
