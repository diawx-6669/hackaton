"""Шаг 6 ТЗ: описание кампуса, написанное LLM строго по найденным источникам.

Главное правило ТЗ: «LLM не должна придумывать факты: пишет только по
найденным текстам и со ссылками». Поэтому:

1. В модель уходит пронумерованный список фактов, собранных нашим же
   конвейером, и ничего больше — ни общих знаний, ни поиска.
2. Ответ приходит структурированным: текст + список утверждений с
   идентификатором источника.
3. Каждую ссылку мы проверяем на своей стороне. Утверждение, сославшееся
   на источник, которого в списке нет, отбрасывается, а описание
   помечается как частично непроверенное. Модель не может «дописать»
   факт незаметно.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from app.config import get_settings
from app.models import Photo, University

log = logging.getLogger(__name__)

MAX_FACTS = 60
MAX_TOKENS = 2000

RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "summary": {
            "type": "string",
            "description": "4–6 предложений о кампусе на русском языке",
        },
        "claims": {
            "type": "array",
            "description": "Каждое утверждение из summary и источник, на котором оно основано",
            "items": {
                "type": "object",
                "properties": {
                    "claim": {"type": "string"},
                    "source_id": {"type": "string"},
                },
                "required": ["claim", "source_id"],
                "additionalProperties": False,
            },
        },
        "insufficient_data": {
            "type": "boolean",
            "description": "true, если фактов не хватает на честное описание",
        },
    },
    "required": ["summary", "claims", "insufficient_data"],
    "additionalProperties": False,
}

SYSTEM = """Ты пишешь краткое описание университетского кампуса для справочного сервиса.

Жёсткие правила:
- Используй ТОЛЬКО факты из пронумерованного списка ниже. Ничего из общих знаний.
- Если фактов не хватает на 4 предложения, поставь insufficient_data = true
  и напиши коротко только то, что подтверждено.
- Каждое утверждение в summary должно опираться на факт из списка; укажи его
  идентификатор в claims.
- Не оценивай качество образования, не сравнивай вузы, не рекламируй.
- Не придумывай числа, даты и названия, которых нет в списке.
- Пиши по-русски, нейтрально, без восторженных прилагательных."""


@dataclass
class Description:
    summary: str
    claims: list[dict[str, str]] = field(default_factory=list)
    sources: list[dict[str, str]] = field(default_factory=list)
    insufficient_data: bool = False
    unverified_claims: list[str] = field(default_factory=list)
    model: str = ""


def build_facts(uni: University, photos: list[Photo]) -> list[dict[str, str]]:
    """Пронумерованные факты из нашего конвейера — единственный вход для LLM."""
    facts: list[dict[str, str]] = []

    def add(fid: str, text: str, url: str) -> None:
        if text and len(facts) < MAX_FACTS:
            facts.append({"id": fid, "text": text, "url": url})

    add("wd-name", f"Название вуза: {uni.name}", uni.wikidata_url)
    if uni.description:
        add("wd-desc", f"Описание в Wikidata: {uni.description}", uni.wikidata_url)
    if uni.city:
        location = uni.city + (f", {uni.country}" if uni.country else "")
        add("wd-city", f"Расположение: {location}", uni.wikidata_url)
    if uni.inception:
        add("wd-inception", f"Дата основания: {uni.inception}", uni.wikidata_url)
    if uni.website:
        add("wd-site", f"Официальный сайт: {uni.website}", uni.website)

    # Категории подтверждённых фото — это факт о том, что мы нашли, а не оценка.
    by_category: dict[str, int] = {}
    for photo in photos:
        by_category[photo.category.value] = by_category.get(photo.category.value, 0) + 1
    for category, count in sorted(by_category.items(), key=lambda kv: -kv[1]):
        add(
            f"cat-{category}",
            f"Найдено подтверждённых фотографий категории «{category}»: {count}",
            uni.wikidata_url,
        )

    for photo in photos[:30]:
        text = photo.description or photo.title
        add(f"photo-{photo.id}", f"Подпись к фотографии: {text}", photo.source_page_url)

    return facts


def _validate(raw: dict[str, Any], facts: list[dict[str, str]]) -> Description:
    """Отбрасывает утверждения, сославшиеся на несуществующий источник."""
    known = {f["id"]: f for f in facts}
    claims: list[dict[str, str]] = []
    unverified: list[str] = []

    for item in raw.get("claims") or []:
        claim = str(item.get("claim", "")).strip()
        source_id = str(item.get("source_id", "")).strip()
        if not claim:
            continue
        if source_id in known:
            claims.append({"claim": claim, "source_id": source_id, "url": known[source_id]["url"]})
        else:
            # Ссылка на источник, которого мы не давали, — выдуманная.
            unverified.append(claim)

    used = {c["source_id"] for c in claims}
    return Description(
        summary=str(raw.get("summary", "")).strip(),
        claims=claims,
        sources=[{"id": f["id"], "text": f["text"], "url": f["url"]} for f in facts if f["id"] in used],
        insufficient_data=bool(raw.get("insufficient_data")) or not claims,
        unverified_claims=unverified,
    )


async def describe(uni: University, photos: list[Photo]) -> Optional[Description]:
    """Возвращает описание или None, если LLM не подключена/не ответила."""
    settings = get_settings()
    if not settings.llm_enabled:
        return None

    facts = build_facts(uni, photos)
    if len(facts) < 3:
        return None

    import anthropic

    client = anthropic.AsyncAnthropic()
    prompt = (
        "Факты, найденные сервисом. Другого источника у тебя нет:\n\n"
        + "\n".join(f"[{f['id']}] {f['text']}" for f in facts)
        + "\n\nНапиши описание кампуса по этим фактам."
    )

    try:
        response = await client.beta.messages.create(
            model=settings.llm_model,
            max_tokens=MAX_TOKENS,
            system=SYSTEM,
            messages=[{"role": "user", "content": prompt}],
            output_config={"format": {"type": "json_schema", "schema": RESPONSE_SCHEMA}},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
    except Exception as exc:  # noqa: BLE001 — описание не должно ронять профиль
        log.warning("LLM-описание не получено: %s", exc)
        return None

    if getattr(response, "stop_reason", None) == "refusal":
        log.info("LLM отказалась описывать кампус")
        return None

    try:
        text = next(b.text for b in response.content if b.type == "text")
        raw = json.loads(text)
    except (StopIteration, ValueError, AttributeError) as exc:
        log.warning("Ответ LLM не разобран: %s", exc)
        return None

    result = _validate(raw, facts)
    result.model = settings.llm_model
    return result
