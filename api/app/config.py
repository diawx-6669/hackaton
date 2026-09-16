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

    wikidata_api: str = "https://www.wikidata.org/w/api.php"
    wikidata_sparql: str = "https://query.wikidata.org/sparql"
    commons_api: str = "https://commons.wikimedia.org/w/api.php"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
