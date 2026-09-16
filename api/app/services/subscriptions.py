"""Заявки на вузы, которых пока нет в выдаче.

Отправку письма мы НЕ изображаем: без настроенного почтового провайдера
заявка только сохраняется, и API прямо об этом сообщает (delivery=stored_only).
Обещать пользователю письмо, которое никуда не уйдёт, — то же самое враньё,
что и поддельные источники.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)
_lock = asyncio.Lock()


class SubscriptionStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _read(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            log.warning("не удалось прочитать заявки: %s", exc)
            return []

    async def add(self, email: str, university: str, comment: str | None) -> int:
        async with _lock:
            items = self._read()
            # Повторная заявка на тот же вуз с той же почты не дублируется.
            key = (email.lower(), university.strip().lower())
            if any((i.get("email", "").lower(), i.get("university", "").lower()) == key for i in items):
                return len(items)

            items.append(
                {
                    "email": email,
                    "university": university.strip(),
                    "comment": (comment or "").strip() or None,
                    "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                }
            )
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
            tmp.replace(self.path)
            return len(items)

    async def count(self) -> int:
        async with _lock:
            return len(self._read())
