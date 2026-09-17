"""Регистрация, вход и текущий пользователь."""
from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Optional

from fastapi import APIRouter, Header, HTTPException

from app.config import get_settings
from app.models import AuthResponse, LoginRequest, RegisterRequest, UserPublic
from app.services.auth import AuthError, UserStore, generate_secret, public

log = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


@lru_cache
def _store() -> UserStore:
    settings = get_settings()
    secret = settings.auth_secret
    if not secret:
        # Без заданного секрета сессии живут до перезапуска процесса.
        secret = generate_secret()
        log.warning(
            "CAMPUSLENS_AUTH_SECRET не задан: сгенерирован временный секрет, "
            "после перезапуска сервиса все пользователи разлогинятся."
        )
    return UserStore(Path(settings.users_path), secret)


async def current_user(authorization: str | None) -> Optional[dict]:
    """Пользователь по заголовку Authorization: Bearer <token>, или None."""
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    user_id = _store().read_token(token)
    if not user_id:
        return None
    return await _store().by_id(user_id)


@router.post("/register", response_model=AuthResponse, status_code=201)
async def register(payload: RegisterRequest) -> AuthResponse:
    try:
        user = await _store().register(payload.email, payload.password, payload.name)
    except AuthError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=503, detail=f"Не удалось сохранить: {exc}") from exc

    return AuthResponse(token=_store().issue_token(user["id"]), user=UserPublic(**public(user)))


@router.post("/login", response_model=AuthResponse)
async def login(payload: LoginRequest) -> AuthResponse:
    try:
        user = await _store().authenticate(payload.email, payload.password)
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    return AuthResponse(token=_store().issue_token(user["id"]), user=UserPublic(**public(user)))


@router.get("/me", response_model=UserPublic)
async def me(authorization: Annotated[str | None, Header()] = None) -> UserPublic:
    user = await current_user(authorization)
    if user is None:
        raise HTTPException(status_code=401, detail="Не авторизован")
    return UserPublic(**public(user))
