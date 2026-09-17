"""GET /api/profile — SSE-стриминг этапов сборки профиля (шаг 3 ТЗ)."""
from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, HTTPException, Query, Request
from sse_starlette.sse import EventSourceResponse

from app.deps import AuthedUser
from app.models import Profile, Stage
from app.pipeline import build_profile, stream_profile

log = logging.getLogger(__name__)
router = APIRouter(tags=["profile"])


def _validate(q: str | None, id: str | None) -> None:
    if not q and not id:
        raise HTTPException(status_code=422, detail="Нужен параметр q (название) или id (Wikidata QID)")


@router.get("/profile")
async def profile_stream(
    request: Request,
    user: AuthedUser,
    q: str | None = Query(None, min_length=2, max_length=200),
    id: str | None = Query(None, pattern=r"^Q\d+$", description="Wikidata QID, если вуз уже выбран"),
    qid: str | None = Query(None, pattern=r"^Q\d+$", description="Синоним id (как в ТЗ)"),
) -> EventSourceResponse:
    """Server-Sent Events. Каждое событие — этап воронки с таймером."""
    id = id or qid
    _validate(q, id)

    async def event_source():
        try:
            async for event in stream_profile(q=q, qid=id):
                if await request.is_disconnected():
                    break
                yield {
                    "event": event.stage.value,
                    "data": json.dumps(event.model_dump(mode="json"), ensure_ascii=False),
                }
        except asyncio.CancelledError:  # клиент ушёл — это нормально
            raise
        except Exception as exc:  # noqa: BLE001
            log.exception("profile stream failed")
            yield {
                "event": Stage.ERROR.value,
                "data": json.dumps(
                    {"stage": Stage.ERROR.value, "message": str(exc), "elapsed_ms": 0},
                    ensure_ascii=False,
                ),
            }

    return EventSourceResponse(event_source(), ping=5)


@router.get("/profile.json", response_model=Profile)
async def profile_json(
    user: AuthedUser,
    q: str | None = Query(None, min_length=2, max_length=200),
    id: str | None = Query(None, pattern=r"^Q\d+$"),
    qid: str | None = Query(None, pattern=r"^Q\d+$"),
) -> Profile:
    """Тот же конвейер, но одним ответом — удобно для тестов и curl."""
    id = id or qid
    _validate(q, id)
    profile, last = await build_profile(q=q, qid=id)
    if profile is not None:
        return profile
    if last.payload and last.payload.get("needs_choice"):
        raise HTTPException(
            status_code=300,
            detail={"message": last.message, "candidates": last.payload["candidates"]},
        )
    raise HTTPException(status_code=404, detail=last.message)
