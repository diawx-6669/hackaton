/**
 * Анонимный идентификатор устройства. Аккаунтов в проекте нет, поэтому
 * «свои фото» определяются этим значением из localStorage.
 *
 * Прямое следствие, о котором сказано в интерфейсе: очистка данных
 * браузера обнуляет историю и бонусы, а от накрутки это не защищает.
 */
const KEY = "campuslens-device-id";

export function getDeviceId(): string {
  if (typeof window === "undefined") return "";
  try {
    const existing = window.localStorage.getItem(KEY);
    if (existing) return existing;
    const fresh =
      typeof crypto !== "undefined" && "randomUUID" in crypto
        ? crypto.randomUUID()
        : `dev-${Math.random().toString(36).slice(2)}${Date.now().toString(36)}`;
    window.localStorage.setItem(KEY, fresh);
    return fresh;
  } catch {
    // Приватный режим или заблокированное хранилище — работаем разово.
    return `dev-temp-${Date.now().toString(36)}`;
  }
}
