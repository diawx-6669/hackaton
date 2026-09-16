"""GET /api/compare — сравнение двух вузов (п.8 ТЗ).

Оба профиля собираются параллельно, поэтому сравнение занимает столько же,
сколько один профиль, а не вдвое больше.
"""
from __future__ import annotations

import asyncio
import time

from fastapi import APIRouter, HTTPException, Query

from app.models import Comparison, ComparisonRow, Profile
from app.pipeline import build_profile

router = APIRouter(tags=["compare"])


def _fmt_int(value: int) -> str:
    return str(value)


def _compare_numbers(a: float, b: float, higher_is_better: bool = True) -> str:
    if a == b:
        return "tie"
    better_is_a = a > b if higher_is_better else a < b
    return "a" if better_is_a else "b"


def _rows(a: Profile, b: Profile) -> list[ComparisonRow]:
    rows: list[ComparisonRow] = [
        ComparisonRow(
            key="city",
            label="Город",
            a=a.university.city or "—",
            b=b.university.city or "—",
        ),
        ComparisonRow(
            key="verified",
            label="Проверенных фото",
            a=_fmt_int(len(a.verified)),
            b=_fmt_int(len(b.verified)),
            winner=_compare_numbers(len(a.verified), len(b.verified)),
        ),
        ComparisonRow(
            key="categories",
            label="Категорий с фото",
            a=_fmt_int(sum(1 for c in a.by_category if c.photos)),
            b=_fmt_int(sum(1 for c in b.by_category if c.photos)),
            winner=_compare_numbers(
                sum(1 for c in a.by_category if c.photos),
                sum(1 for c in b.by_category if c.photos),
            ),
        ),
        ComparisonRow(
            key="needs_review",
            label="Требуют проверки",
            a=_fmt_int(len(a.needs_review)),
            b=_fmt_int(len(b.needs_review)),
        ),
        ComparisonRow(
            key="rejected",
            label="Отклонено",
            a=_fmt_int(len(a.rejected)),
            b=_fmt_int(len(b.rejected)),
        ),
        ComparisonRow(
            key="took",
            label="Время сборки",
            a=f"{a.took_ms / 1000:.1f} с",
            b=f"{b.took_ms / 1000:.1f} с",
            winner=_compare_numbers(a.took_ms, b.took_ms, higher_is_better=False),
        ),
    ]

    avg_a = sum(p.confidence for p in a.verified) / len(a.verified) if a.verified else 0.0
    avg_b = sum(p.confidence for p in b.verified) / len(b.verified) if b.verified else 0.0
    rows.insert(
        2,
        ComparisonRow(
            key="confidence",
            label="Средний Confidence",
            a=f"{round(avg_a * 100)}%" if a.verified else "нет данных",
            b=f"{round(avg_b * 100)}%" if b.verified else "нет данных",
            winner=_compare_numbers(avg_a, avg_b) if (a.verified and b.verified) else None,
        ),
    )
    return rows


async def _one(q: str | None, qid: str | None, side: str) -> Profile:
    profile, last = await build_profile(q=q, qid=qid)
    if profile is None:
        detail = last.message
        if last.payload and last.payload.get("needs_choice"):
            detail = f"{last.message} (сторона «{side}»): уточните вуз через /api/resolve"
        raise HTTPException(status_code=404, detail=f"[{side}] {detail}")
    return profile


@router.get("/compare", response_model=Comparison)
async def compare(
    a: str | None = Query(None, min_length=2, description="Название первого вуза"),
    b: str | None = Query(None, min_length=2, description="Название второго вуза"),
    a_id: str | None = Query(None, pattern=r"^Q\d+$"),
    b_id: str | None = Query(None, pattern=r"^Q\d+$"),
) -> Comparison:
    if not (a or a_id) or not (b or b_id):
        raise HTTPException(status_code=422, detail="Нужны оба вуза: a/a_id и b/b_id")

    started = time.perf_counter()
    profile_a, profile_b = await asyncio.gather(
        _one(a, a_id, "a"),
        _one(b, b_id, "b"),
    )
    return Comparison(
        a=profile_a,
        b=profile_b,
        rows=_rows(profile_a, profile_b),
        took_ms=int((time.perf_counter() - started) * 1000),
    )
