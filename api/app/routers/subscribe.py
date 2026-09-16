"""POST /api/subscribe — заявка «не нашли свой вуз»."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.models import SubscribeRequest, SubscribeResponse
from app.services.subscriptions import SubscriptionStore

router = APIRouter(tags=["subscribe"])


@lru_cache
def _store() -> SubscriptionStore:
    return SubscriptionStore(Path(get_settings().subscriptions_path))


@router.post("/subscribe", response_model=SubscribeResponse)
async def subscribe(payload: SubscribeRequest) -> SubscribeResponse:
    settings = get_settings()
    try:
        size = await _store().add(payload.email, payload.university, payload.comment)
    except OSError as exc:
        raise HTTPException(status_code=503, detail=f"Не удалось сохранить заявку: {exc}") from exc

    # Письмо уйдёт только если реально настроен провайдер. Иначе не обещаем.
    mail_configured = bool(settings.smtp_host and settings.smtp_from)
    if mail_configured:
        return SubscribeResponse(
            ok=True,
            message="Заявка принята — пришлём отчёт, когда соберём данные по вузу.",
            delivery="queued",
            queue_size=size,
        )

    return SubscribeResponse(
        ok=True,
        message=(
            "Заявка сохранена. Почтовая рассылка пока не подключена, "
            "поэтому письмо придёт не автоматически — мы свяжемся вручную."
        ),
        delivery="stored_only",
        queue_size=size,
    )
