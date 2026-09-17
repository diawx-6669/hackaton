"""Шаг 3 ТЗ: конвейер сборки профиля + живая воронка через SSE.

Все сборщики стартуют параллельно (asyncio), общий бюджет — CAMPUSLENS_TOTAL_TIMEOUT
(по умолчанию 25 с при требовании «до 30 секунд»). Что не успело — не блокирует
ответ: отдаём то, что собрали, и честно пишем об этом в warnings.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import AsyncIterator, Awaitable, Callable, Optional

from app.config import get_settings
from app.models import (
    CampusDescription,
    CategoryBucket,
    RejectReason,
    SiteText,
    Photo,
    PhotoCategory,
    Profile,
    Stage,
    StageEvent,
    University,
)
from app.services import commons, dedup, describe, evidence, officialsite, wikidata
from app.services.classify import classify

log = logging.getLogger(__name__)

# Порядок вкладок галереи на фронте (класс JUNK в UI не показывается).
GALLERY_CATEGORIES = [
    PhotoCategory.CAMPUS,
    PhotoCategory.DORMS,
    PhotoCategory.CLASSROOMS,
    PhotoCategory.LIBRARIES,
    PhotoCategory.LABS,
    PhotoCategory.SPORTS,
    PhotoCategory.STUDENT_LIFE,
    PhotoCategory.CITY,
]

Collector = tuple[str, Callable[[], Awaitable[list[Photo]]]]

# Человеческие названия причин отказа для строки воронки (п.«Интерфейс» ТЗ).
REJECT_LABELS: dict[str, str] = {
    RejectReason.DUPLICATE.value: "дубли",
    RejectReason.NOT_THIS_UNIVERSITY.value: "не тот вуз",
    RejectReason.STOCK_DOMAIN.value: "стоки",
    RejectReason.NOT_A_PHOTO.value: "не фотографии",
    RejectReason.TOO_FAR.value: "далеко от кампуса",
    RejectReason.NO_LICENSE.value: "без лицензии",
    RejectReason.TOO_SMALL.value: "мелкие",
    RejectReason.JUNK_CLASS.value: "логотипы и схемы",
    RejectReason.LOW_CONFIDENCE.value: "низкий балл",
}


class Clock:
    def __init__(self) -> None:
        self.started = time.perf_counter()

    @property
    def elapsed_ms(self) -> int:
        return int((time.perf_counter() - self.started) * 1000)

    def remaining(self, budget: float) -> float:
        return max(0.0, budget - (time.perf_counter() - self.started))


async def _resolve_target(q: str | None, qid: str | None) -> tuple[Optional[University], list[University]]:
    """Возвращает (выбранный вуз, кандидаты). Если выбор неоднозначен — вуза нет."""
    if qid:
        details = await wikidata.fetch_details([qid])
        det = details.get(qid)
        if not det:
            return None, []
        coords = wikidata.parse_point(det.get("coord")) or wikidata.parse_point(
            det.get("city_coord")
        )
        name = det.get("label") or qid
        uni = University(
            id=qid,
            name=name,
            description=det.get("description"),
            aliases=wikidata._merge_aliases(name, [], det),
            city=det.get("city"),
            country=det.get("country"),
            coordinates=coords,
            website=det.get("website"),
            commons_category=det.get("commons_category"),
            logo_url=det.get("logo"),
            inception=(det.get("inception") or "")[:10] or None,
            wikidata_url=f"https://www.wikidata.org/wiki/{qid}",
            match_score=1.0,
        )
        return uni, [uni]

    candidates = await wikidata.resolve(q or "", limit=8)
    if not candidates:
        return None, []
    if wikidata.is_ambiguous(candidates):
        return None, candidates
    return candidates[0], candidates


def _build_collectors(uni: University) -> list[Collector]:
    collectors: list[Collector] = []

    if uni.commons_category:
        async def by_category() -> list[Photo]:
            return await commons.collect(
                commons_category=uni.commons_category, coordinates=None
            )

        collectors.append((f"Commons: категория «{uni.commons_category}»", by_category))

    if uni.coordinates:
        coords = uni.coordinates

        async def by_geo() -> list[Photo]:
            return await commons.collect(commons_category=None, coordinates=coords)

        radius = get_settings().geosearch_radius
        collectors.append((f"Commons: геопоиск в радиусе {radius} м", by_geo))

    # Поиск по названию работает даже у вузов без категории и без координат —
    # без него профиль малоизвестного вуза оставался бы пустым.
    search_terms = [uni.name, *[a for a in uni.aliases if len(a) > 4]][:2]
    for term in search_terms:

        def by_search(query: str = term) -> Awaitable[list[Photo]]:
            return commons.collect(
                commons_category=None, coordinates=None, search_query=query
            )

        collectors.append((f"Commons: поиск «{term}»", by_search))

    if uni.website:
        site = uni.website
        name = uni.name

        async def by_site() -> list[Photo]:
            return await officialsite.collect(site, name)

        host = site.split("//")[-1].split("/")[0]
        collectors.append((f"Сайт вуза: {host}", by_site))

    # Шаг 8 ТЗ: сюда же подключается поисковый API картинок.
    return collectors


def _make_buckets(photos: list[Photo], classification_ready: bool) -> list[CategoryBucket]:
    buckets: list[CategoryBucket] = []
    for cat in GALLERY_CATEGORIES:
        items = [p for p in photos if p.category == cat]
        empty_reason = None
        if not items:
            empty_reason = (
                f"Подтверждённых фото по категории «{cat.value}» не найдено"
                if classification_ready
                else "Классификация по категориям подключается на шаге 5 — фото пока не разнесены"
            )
        buckets.append(CategoryBucket(category=cat, photos=items, empty_reason=empty_reason))

    unsorted = [p for p in photos if p.category == PhotoCategory.UNKNOWN]
    if unsorted:
        buckets.append(
            CategoryBucket(
                category=PhotoCategory.UNKNOWN,
                photos=unsorted,
                empty_reason=None,
            )
        )
    return buckets


async def build_profile(q: str | None = None, qid: str | None = None) -> tuple[Optional[Profile], StageEvent]:
    """Прогоняет тот же конвейер до конца и отдаёт готовый профиль.

    Возвращает (профиль, последнее событие): по последнему событию видно,
    что именно случилось — ошибка, требование выбрать вуз или успех.
    """
    last: StageEvent | None = None
    profile: Profile | None = None
    async for event in stream_profile(q=q, qid=qid):
        last = event
        if event.stage is Stage.DONE and event.payload:
            profile = Profile.model_validate(event.payload)
    assert last is not None
    return profile, last


async def stream_profile(q: str | None = None, qid: str | None = None) -> AsyncIterator[StageEvent]:
    """Асинхронный генератор этапов: найдено → дубли → отклонено → проверено."""
    settings = get_settings()
    clock = Clock()
    warnings: list[str] = []

    yield StageEvent(
        stage=Stage.COLLECTING,
        message="Ищем вуз в Wikidata…",
        elapsed_ms=clock.elapsed_ms,
    )

    try:
        uni, candidates = await asyncio.wait_for(
            _resolve_target(q, qid), timeout=min(12.0, settings.total_timeout)
        )
    except asyncio.TimeoutError:
        yield StageEvent(
            stage=Stage.ERROR,
            message="Wikidata не ответила за отведённое время",
            elapsed_ms=clock.elapsed_ms,
        )
        return
    except Exception as exc:  # noqa: BLE001
        log.exception("resolve failed")
        yield StageEvent(
            stage=Stage.ERROR, message=f"Ошибка поиска вуза: {exc}", elapsed_ms=clock.elapsed_ms
        )
        return

    if uni is None and candidates:
        yield StageEvent(
            stage=Stage.RESOLVED,
            message="Нашлось несколько подходящих вузов — уточните выбор",
            elapsed_ms=clock.elapsed_ms,
            counts={"candidates": len(candidates)},
            payload={
                "needs_choice": True,
                "candidates": [c.model_dump(mode="json") for c in candidates],
            },
        )
        return

    if uni is None:
        yield StageEvent(
            stage=Stage.ERROR,
            message=f"По запросу «{q or qid}» вуз в Wikidata не найден",
            elapsed_ms=clock.elapsed_ms,
        )
        return

    yield StageEvent(
        stage=Stage.RESOLVED,
        message=f"Вуз определён: {uni.name}",
        elapsed_ms=clock.elapsed_ms,
        payload={"needs_choice": False, "university": uni.model_dump(mode="json")},
    )

    if not uni.commons_category:
        warnings.append("У вуза в Wikidata не указана категория Commons (P373) — источников меньше")
    if not uni.coordinates:
        warnings.append("У вуза в Wikidata нет координат (P625) — геопоиск и геоулики недоступны")

    collectors = _build_collectors(uni)
    if not collectors:
        yield StageEvent(
            stage=Stage.DONE,
            message="Нет ни одного доступного источника для этого вуза",
            elapsed_ms=clock.elapsed_ms,
            payload=Profile(
                university=uni, verified=[], warnings=warnings, took_ms=clock.elapsed_ms
            ).model_dump(mode="json"),
        )
        return

    yield StageEvent(
        stage=Stage.COLLECTING,
        message=f"Запускаем параллельно источников: {len(collectors)}",
        elapsed_ms=clock.elapsed_ms,
        counts={"sources": len(collectors)},
        payload={"sources": [name for name, _ in collectors]},
    )

    # --- параллельный сбор с общим дедлайном ---
    tasks: dict[asyncio.Task[list[Photo]], str] = {}
    for name, fn in collectors:
        tasks[asyncio.create_task(fn())] = name

    # Текст с сайта вуза нужен только под конец, но качать его тогда же —
    # значит добавить секунды в самый конец. Запускаем сразу, заберём готовым.
    site_task: asyncio.Task[list[SiteText]] | None = None
    if uni.website:
        site_task = asyncio.create_task(officialsite.collect_texts(uni.website))

    collected: list[Photo] = []
    pending = set(tasks)
    while pending:
        remaining = clock.remaining(settings.total_timeout)
        if remaining <= 0:
            break
        done, pending = await asyncio.wait(
            pending, timeout=remaining, return_when=asyncio.FIRST_COMPLETED
        )
        if not done:
            break
        for task in done:
            name = tasks[task]
            try:
                photos = task.result()
            except Exception as exc:  # noqa: BLE001
                log.warning("collector %s failed: %s", name, exc)
                warnings.append(f"Источник «{name}» не ответил: {exc}")
                continue
            collected.extend(photos)
            yield StageEvent(
                stage=Stage.FOUND,
                message=f"{name}: {len(photos)} файлов",
                elapsed_ms=clock.elapsed_ms,
                counts={"found_total": len(collected), "from_source": len(photos)},
            )

    if site_task is not None and site_task.done() and site_task.exception():
        site_task.exception()  # забираем исключение, чтобы asyncio не ругался

    if pending:
        for task in pending:
            task.cancel()
            warnings.append(
                f"Источник «{tasks[task]}» не уложился в {settings.total_timeout:.0f} с"
            )
        # Дожидаемся отмены, иначе asyncio сыпет «Task exception was never retrieved».
        await asyncio.gather(*pending, return_exceptions=True)

    yield StageEvent(
        stage=Stage.FOUND,
        message=f"Найдено файлов: {len(collected)}",
        elapsed_ms=clock.elapsed_ms,
        counts={"found": len(collected)},
    )

    # --- точная дедупликация ---
    # Перцептивная идёт ПОСЛЕ отсева: качать миниатюры того, что всё равно
    # выбросим (логотипы, стоки, чужие здания), — трата самой дорогой части
    # бюджета. Обычно это срезает больше половины загрузок.
    unique, duplicates = dedup.exact_dedupe(collected)

    # --- классификация по категориям ---
    for photo in unique:
        result = classify(photo)
        if result.category is not PhotoCategory.UNKNOWN:
            photo.category = result.category
            photo.category_source = "metadata"
            photo.category_terms = result.matched
            photo.evidence.classifier_confidence = result.confidence

    classified = sum(1 for p in unique if p.category is not PhotoCategory.UNKNOWN)
    yield StageEvent(
        stage=Stage.CLASSIFIED,
        message=f"Категории определены: {classified} из {len(unique)}",
        elapsed_ms=clock.elapsed_ms,
        counts={"classified": classified, "unclassified": len(unique) - classified},
    )

    # --- оценка достоверности ---
    names = [uni.name, *uni.aliases]
    if uni.commons_category:
        names.append(uni.commons_category)
    scored = [evidence.score_photo(p, uni.coordinates, uni.website, names) for p in unique]
    # Дубли тоже считаем: причина отказа у них уже стоит и не перезапишется,
    # зато в карточке будет нормальный разбор улик, а не пустой блок.
    for duplicate in duplicates:
        evidence.score_photo(duplicate, uni.coordinates, uni.website, names)

    verified: list[Photo] = []
    needs_review: list[Photo] = []
    rejected: list[Photo] = list(duplicates)
    for photo in scored:
        place = evidence.bucket(photo)
        if place == "verified":
            verified.append(photo)
        elif place == "needs_review":
            needs_review.append(photo)
        else:
            rejected.append(photo)

    # --- перцептивная дедупликация только среди прошедших отбор ---
    survivors = [*verified, *needs_review]
    perceptual: list[Photo] = []
    if survivors:
        try:
            kept, perceptual = await asyncio.wait_for(
                dedup.perceptual_dedupe(survivors),
                timeout=max(2.0, clock.remaining(settings.total_timeout) - 3.0),
            )
        except asyncio.TimeoutError:
            kept = survivors
            warnings.append(
                "pHash-дедупликация не уложилась в бюджет — схлопнуты только одинаковые файлы"
            )

        # Схлопнутый дубль мог принести своему представителю ещё один источник,
        # а это улика. Пересчитываем балл только у таких — это чистый CPU.
        for photo in kept:
            if photo.evidence.source_count != len(photo.source_kinds):
                evidence.score_photo(photo, uni.coordinates, uni.website, names)

        verified = [p for p in kept if evidence.bucket(p) == "verified"]
        needs_review = [p for p in kept if evidence.bucket(p) == "needs_review"]
        rejected.extend(perceptual)

    duplicates = [*duplicates, *perceptual]

    yield StageEvent(
        stage=Stage.DEDUPED,
        message=f"Дубли удалены: −{len(duplicates)}",
        elapsed_ms=clock.elapsed_ms,
        counts={"unique": len(unique), "duplicates": len(duplicates)},
    )

    verified.sort(key=lambda p: p.confidence, reverse=True)
    needs_review.sort(key=lambda p: p.confidence, reverse=True)

    reject_counts: dict[str, int] = {}
    for photo in rejected:
        key = photo.reject_reason.value if photo.reject_reason else "unknown"
        reject_counts[key] = reject_counts.get(key, 0) + 1

    yield StageEvent(
        stage=Stage.REJECTED,
        message="Отклонено: " + (
            ", ".join(
                f"{REJECT_LABELS.get(k, k)} −{v}"
                for k, v in sorted(reject_counts.items(), key=lambda kv: -kv[1])
            )
            or "ничего"
        ),
        elapsed_ms=clock.elapsed_ms,
        counts={"rejected": len(rejected), **reject_counts},
    )

    if not verified and not needs_review:
        warnings.append("Ни одного подтверждённого фото собрать не удалось — смотрите вкладку «Отклонено»")

    # --- описание кампуса (шаг 6 ТЗ) ---
    description: CampusDescription | None = None
    if verified or needs_review:
        # Текст с сайта вуза — страницы уже скачаны сборщиком фотографий,
        # поэтому второй раз в сеть не идём: обход закеширован.
        site_texts: list[SiteText] = []
        if site_task is not None:
            try:
                site_texts = await asyncio.wait_for(
                    asyncio.shield(site_task),
                    timeout=max(0.5, min(3.0, clock.remaining(settings.total_timeout))),
                )
            except (asyncio.TimeoutError, Exception):  # noqa: BLE001
                site_texts = []

        try:
            result = await asyncio.wait_for(
                describe.describe(uni, verified or needs_review, site_texts),
                timeout=max(1.0, clock.remaining(settings.total_timeout)),
            )
        except asyncio.TimeoutError:
            result = None
            warnings.append("Описание кампуса не уложилось в бюджет времени")

        if result is not None:
            description = CampusDescription(
                summary=result.summary,
                claims=[dict(c) for c in result.claims],  # type: ignore[arg-type]
                sources=result.sources,
                insufficient_data=result.insufficient_data,
                unverified_claims=result.unverified_claims,
                model=result.model,
            )
            if result.unverified_claims:
                warnings.append(
                    f"В описании отброшено утверждений без источника: {len(result.unverified_claims)}"
                )
            yield StageEvent(
                stage=Stage.DESCRIBED,
                message="Описание кампуса собрано по найденным источникам",
                elapsed_ms=clock.elapsed_ms,
                counts={"claims": len(description.claims)},
            )

    profile = Profile(
        university=uni,
        verified=verified,
        needs_review=needs_review,
        rejected=rejected,
        by_category=_make_buckets(verified, classification_ready=True),
        description=description,
        stats={
            "found": len(collected),
            "unique": len(unique),
            "duplicates": len(duplicates),
            "verified": len(verified),
            "needs_review": len(needs_review),
            "rejected": len(rejected),
            "sources": len(collectors),
        },
        warnings=warnings,
        took_ms=clock.elapsed_ms,
    )

    yield StageEvent(
        stage=Stage.VERIFIED,
        message=f"Проверено: {len(verified)} (+{len(needs_review)} требуют проверки)",
        elapsed_ms=clock.elapsed_ms,
        counts={"verified": len(verified), "needs_review": len(needs_review)},
    )
    yield StageEvent(
        stage=Stage.DONE,
        message=f"Готово за {clock.elapsed_ms / 1000:.1f} с",
        elapsed_ms=clock.elapsed_ms,
        counts=profile.stats,
        payload=profile.model_dump(mode="json"),
    )
