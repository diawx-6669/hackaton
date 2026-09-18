"""Конфигурация сервиса. Всё читается из окружения / .env — никаких ключей в коде."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CAMPUSLENS_",
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Wikimedia требует контактный User-Agent, иначе быстро прилетает 429.
    user_agent: str = "CampusLens-AI/0.1 (hackathon LOCUS 2026; contact: set CAMPUSLENS_USER_AGENT)"

    # Бюджет времени: весь профиль обязан уложиться в 30 с, целимся в 25 с.
    total_timeout: float = 25.0
    # Бюджет ПЕРВОГО показа: через столько секунд отдаём то, что уже собрано,
    # и продолжаем добирать остальное в фоне. Пользователь видит фотографии
    # почти сразу, а не ждёт самый медленный источник.
    first_paint_budget: float = 3.0
    http_timeout: float = 10.0

    max_files_per_source: int = 120
    geosearch_radius: int = 1000  # метры
    category_depth: int = 2

    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # Кеш: экономит время жюри на повторных запросах и бережёт лимиты Wikimedia.
    cache_enabled: bool = True
    cache_dir: str = "data/cache"
    cache_ttl_resolve: float = 86400.0   # метаданные вуза меняются редко
    cache_ttl_photos: float = 21600.0    # состав категории Commons — чаще

    # Заявки «не нашли свой вуз». Письма уходят, только если задан SMTP.
    subscriptions_path: str = "data/subscriptions.json"
    # Фото от студентов. На бесплатных тарифах диск эфемерный —
    # после передеплоя каталог пуст, об этом сказано в интерфейсе.
    upload_dir: str = "data/uploads"
    # Учётные записи. Секрет подписи сессий обязателен на проде:
    # без него после каждого перезапуска все разлогиниваются.
    users_path: str = "data/users.json"
    auth_secret: str = ""
    # Требовать вход для поиска и профилей. Выключается для локальной отладки.
    require_auth: bool = True
    # Демо-аккаунт для жюри: создаётся при старте, если задан.
    # Формат: "почта:пароль"
    demo_account: str = ""

    # LLM-описание кампуса (шаг 6 ТЗ). Без ключа просто не включается.
    # Провайдер выбирается автоматически по тому, какой ключ задан.
    llm_provider: str = "auto"          # auto | gemini | groq | anthropic
    llm_model: str = "claude-opus-5"    # используется провайдером anthropic
    gemini_model: str = "gemini-3.6-flash"
    gemini_endpoint: str = "https://generativelanguage.googleapis.com/v1beta"
    # Модель Groq задаётся переменной: список актуальных меняется,
    # см. console.groq.com/docs/models
    groq_model: str = "llama-3.3-70b-versatile"
    groq_endpoint: str = "https://api.groq.com/openai/v1"
    smtp_host: str = ""
    smtp_from: str = ""

    wikidata_api: str = "https://www.wikidata.org/w/api.php"
    wikidata_sparql: str = "https://query.wikidata.org/sparql"
    commons_api: str = "https://commons.wikimedia.org/w/api.php"
    # Overpass: окружение кампуса (п.8 ТЗ). Публичный инстанс, ключ не нужен,
    # но есть лимиты — отсюда кеш и всего один ретрай.
    overpass_api: str = "https://overpass-api.de/api/interpreter"
    # OSRM: время в пути. У публичного демо-сервера есть только автомобильный
    # профиль — пешеходные участки поэтому считаются по прямой и так подписаны.
    osrm_endpoint: str = "https://router.project-osrm.org"

    @property
    def active_llm(self) -> tuple[str, str] | None:
        """(провайдер, ключ) или None, если ни одного ключа нет.

        Явно заданный CAMPUSLENS_LLM_PROVIDER важнее автоопределения.
        """
        import os

        keys = {
            "gemini": os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY"),
            "groq": os.environ.get("GROQ_API_KEY"),
            "anthropic": os.environ.get("ANTHROPIC_API_KEY"),
        }

        if self.llm_provider in keys:
            key = keys[self.llm_provider]
            return (self.llm_provider, key) if key else None

        # Автовыбор: первый провайдер, для которого есть ключ.
        for provider in ("gemini", "groq", "anthropic"):
            if keys[provider]:
                return provider, keys[provider]  # type: ignore[return-value]
        return None

    @property
    def llm_enabled(self) -> bool:
        return self.active_llm is not None

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
