"""Регистрация и вход.

Сознательно простая схема: почта, пароль, подписанный токен сессии.
Пароли хранятся только как bcrypt-хеши, в открытом виде не сохраняются
и в логи не попадают.

Ограничение, о котором сказано и в интерфейсе, и в README: на бесплатном
тарифе диск эфемерный, поэтому после передеплоя учётные записи исчезают.
Для продакшена нужна настоящая база.
"""
from __future__ import annotations

import asyncio
import json
import logging
import secrets
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import bcrypt
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

log = logging.getLogger(__name__)

MIN_PASSWORD = 8
MAX_PASSWORD = 128  # bcrypt работает с первыми 72 байтами, длиннее смысла нет
TOKEN_MAX_AGE = 30 * 24 * 3600  # 30 дней
SALT = "campuslens-session"

_lock = asyncio.Lock()


class AuthError(ValueError):
    """Текст показывается пользователю как есть."""


class UserStore:
    def __init__(self, path: Path, secret: str) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._serializer = URLSafeTimedSerializer(secret, salt=SALT)

    def _read(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            log.warning("файл пользователей не прочитан: %s", exc)
            return []

    def _write(self, users: list[dict[str, Any]]) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(users, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(self.path)

    @staticmethod
    def _normalize(email: str) -> str:
        return email.strip().lower()

    def _check_password(self, password: str) -> None:
        if len(password) < MIN_PASSWORD:
            raise AuthError(f"Пароль короче {MIN_PASSWORD} символов")
        if len(password) > MAX_PASSWORD:
            raise AuthError("Слишком длинный пароль")

    async def register(self, email: str, password: str, name: str | None = None) -> dict[str, Any]:
        email = self._normalize(email)
        self._check_password(password)

        async with _lock:
            users = self._read()
            if any(u["email"] == email for u in users):
                raise AuthError("Такая почта уже зарегистрирована")

            user = {
                "id": uuid.uuid4().hex,
                "email": email,
                "name": (name or "").strip()[:60] or email.split("@")[0],
                "password_hash": bcrypt.hashpw(
                    password.encode("utf-8"), bcrypt.gensalt()
                ).decode("ascii"),
                "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
            users.append(user)
            self._write(users)
        return user

    async def authenticate(self, email: str, password: str) -> dict[str, Any]:
        email = self._normalize(email)
        async with _lock:
            users = self._read()

        user = next((u for u in users if u["email"] == email), None)

        # Пароль сверяем даже когда пользователя нет: иначе по времени ответа
        # можно узнать, какие почты зарегистрированы.
        stored = user["password_hash"].encode("ascii") if user else bcrypt.hashpw(
            b"dummy", bcrypt.gensalt()
        )
        ok = bcrypt.checkpw(password.encode("utf-8"), stored)

        if not user or not ok:
            # Одинаковый текст в обоих случаях — не подсказываем, что почта есть.
            raise AuthError("Неверная почта или пароль")
        return user

    async def by_id(self, user_id: str) -> Optional[dict[str, Any]]:
        async with _lock:
            users = self._read()
        return next((u for u in users if u["id"] == user_id), None)

    def issue_token(self, user_id: str) -> str:
        return self._serializer.dumps({"uid": user_id})

    def read_token(self, token: str) -> Optional[str]:
        try:
            data = self._serializer.loads(token, max_age=TOKEN_MAX_AGE)
        except SignatureExpired:
            log.debug("срок токена истёк")
            return None
        except BadSignature:
            log.debug("подпись токена не сошлась")
            return None
        return data.get("uid") if isinstance(data, dict) else None


def public(user: dict[str, Any]) -> dict[str, str]:
    """Что можно отдавать наружу. Хеш пароля сюда не попадает никогда."""
    return {"id": user["id"], "email": user["email"], "name": user["name"]}


def generate_secret() -> str:
    """Временный секрет, если он не задан в окружении."""
    return secrets.token_urlsafe(32)
