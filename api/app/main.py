"""CampusLens AI — FastAPI backend."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.models import HealthResponse
from app.routers import profile, resolve
from app.services.cache import get_cache
from app.services.http import close_client

VERSION = "0.5.0"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
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
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(resolve.router, prefix="/api")
app.include_router(profile.router, prefix="/api")


@app.get("/api/health", response_model=HealthResponse, tags=["meta"])
async def health() -> HealthResponse:
    return HealthResponse(status="ok", version=VERSION, cache=get_cache().stats())
