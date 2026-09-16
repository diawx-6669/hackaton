"""CampusLens AI — FastAPI backend."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.models import HealthResponse
from app.routers import compare, profile, resolve, subscribe
from app.services.cache import get_cache
from app.services.http import close_client

VERSION = "0.6.0"

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
    if all("localhost" in o or "127.0.0.1" in o for o in settings.cors_origin_list):
        log.warning(
            "CAMPUSLENS_CORS_ORIGINS содержит только локальные адреса (%s). "
            "Развёрнутый фронтенд получит ошибку CORS — добавьте его домен.",
            settings.cors_origins,
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    _check_deployment_config(get_settings())
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


@app.get("/api/health", response_model=HealthResponse, tags=["meta"])
async def health() -> HealthResponse:
    return HealthResponse(status="ok", version=VERSION, cache=get_cache().stats())
