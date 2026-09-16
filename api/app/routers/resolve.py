"""GET /api/resolve — поиск вуза по названию (шаг 1 ТЗ)."""
from __future__ import annotations

import time

from fastapi import APIRouter, HTTPException, Query

from app.models import ResolveResponse
from app.services import wikidata

router = APIRouter(tags=["resolve"])


@router.get("/resolve", response_model=ResolveResponse)
async def resolve_university(
    q: str = Query(..., min_length=2, max_length=200, description="Название вуза"),
    limit: int = Query(8, ge=1, le=20),
) -> ResolveResponse:
    started = time.perf_counter()
    try:
        candidates = await wikidata.resolve(q, limit=limit)
    except Exception as exc:  # noqa: BLE001 — наружу отдаём честную 502
        raise HTTPException(
            status_code=502, detail=f"Wikidata недоступна: {exc}"
        ) from exc

    return ResolveResponse(
        query=q,
        ambiguous=wikidata.is_ambiguous(candidates),
        candidates=candidates,
        took_ms=int((time.perf_counter() - started) * 1000),
    )
