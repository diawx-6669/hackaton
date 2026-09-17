"""Общие зависимости FastAPI: требование входа."""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException

from app.config import get_settings
from app.routers.auth import current_user


async def require_user(
    authorization: Annotated[str | None, Header()] = None,
) -> dict:
    """Пускает дальше только вошедшего пользователя.

    Если CAMPUSLENS_REQUIRE_AUTH выключен, проверка не выполняется —
    это нужно, чтобы тесты и локальная отладка не требовали аккаунта.
    """
    if not get_settings().require_auth:
        return {"id": "anonymous", "email": "", "name": "Гость"}

    user = await current_user(authorization)
    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Нужен вход в аккаунт",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


AuthedUser = Annotated[dict, Depends(require_user)]
