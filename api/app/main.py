"""CampusLens AI — FastAPI backend."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.models import HealthResponse
from app.routers import auth, compare, profile, resolve, subscribe, uploads
from app.services.cache import get_cache
from app.services.http import close_client

VERSION = "0.9.0"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


log = logging.getLogger("campuslens")


def _check_deployment_config(settings) -> None:
    """Две ошибки, которые на проде молча ломают сервис. Пусть кричат в логе."""
    if "set CAMPUSLENS_USER_AGENT" in settings.user_agent:
        log.warning(
            "CAMPUSLENS_USER_AGENT не задан. Wikimedia режет анонимные запросы (429) — "
            "укажите контактный User-Agent в переменных окружения."
        )
    if settings.require_auth and not settings.demo_account:
        log.warning(
            "Вход обязателен, но демо-аккаунт не задан. Жюри придётся регистрироваться: "
            "задайте CAMPUSLENS_DEMO_ACCOUNT в формате почта:пароль."
        )
    if not settings.auth_secret:
        log.warning(
            "CAMPUSLENS_AUTH_SECRET не задан — после перезапуска сервиса все "
            "пользователи разлогинятся. Задайте длинную случайную строку."
        )
    if all("localhost" in o or "127.0.0.1" in o for o in settings.cors_origin_list):
        log.warning(
            "CAMPUSLENS_CORS_ORIGINS содержит только локальные адреса (%s). "
            "Развёрнутый фронтенд получит ошибку CORS — добавьте его домен.",
            settings.cors_origins,
        )


async def _ensure_demo_account(settings) -> None:
    """Демо-аккаунт для жюри: сайт закрыт входом, а регистрироваться им незачем."""
    if not settings.demo_account or ":" not in settings.demo_account:
        return

    email, _, password = settings.demo_account.partition(":")
    from app.routers.auth import _store
    from app.services.auth import AuthError

    try:
        await _store().register(email, password, "Демо")
        log.info("демо-аккаунт создан: %s", email)
    except AuthError:
        pass  # уже существует — это нормально
    except OSError as exc:
        log.warning("демо-аккаунт не создан: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    _check_deployment_config(settings)
    await _ensure_demo_account(settings)
    yield
    await close_client()


settings = get_settings()

app = FastAPI(
    title="CampusLens AI API",
    description="Проверенный визуальный профиль кампуса по названию вуза.",
    version=VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(resolve.router, prefix="/api")
app.include_router(profile.router, prefix="/api")
app.include_router(compare.router, prefix="/api")
app.include_router(subscribe.router, prefix="/api")
app.include_router(uploads.router, prefix="/api")
app.include_router(auth.router, prefix="/api")


@app.get("/api/health", response_model=HealthResponse, tags=["meta"])
async def health() -> HealthResponse:
    return HealthResponse(status="ok", version=VERSION, cache=get_cache().stats())
