"""Шаг 6 ТЗ (базовая часть): улики и Confidence Score.

Классификатор CLIP (шаг 5) подключается сюда же — как ещё один сигнал.
Если сигнала нет, он не участвует в сумме, а веса пере-нормируются:
мы не додумываем данные, которых нет.
"""
from __future__ import annotations

import datetime as dt
import math
import re
from typing import Iterable, Optional
from urllib.parse import urlparse

from app.models import (
    Coordinates,
    Evidence,
    EvidenceSignal,
    Photo,
    PhotoCategory,
    RejectReason,
    SourceKind,
)
from app.services.classify import mentions_university

# Человеческие названия категорий для текста улики.
CATEGORY_LABELS: dict[PhotoCategory, str] = {
    PhotoCategory.CAMPUS: "Кампус",
    PhotoCategory.DORMS: "Общежития",
    PhotoCategory.CLASSROOMS: "Аудитории",
    PhotoCategory.LIBRARIES: "Библиотеки",
    PhotoCategory.LABS: "Лаборатории",
    PhotoCategory.SPORTS: "Спорт",
    PhotoCategory.STUDENT_LIFE: "Студенческая жизнь",
    PhotoCategory.CITY: "Город",
    PhotoCategory.JUNK: "Мусор",
    PhotoCategory.UNKNOWN: "Без категории",
}

# Стоковые фотобанки — по ТЗ такие источники отклоняем.
STOCK_DOMAINS = {
    "shutterstock.com", "gettyimages.com", "istockphoto.com", "depositphotos.com",
    "alamy.com", "dreamstime.com", "123rf.com", "stock.adobe.com", "freepik.com",
    "vecteezy.com", "canstockphoto.com", "bigstockphoto.com", "unsplash.com",
    "pexels.com", "pixabay.com",
}

WIKIMEDIA_DOMAINS = {"commons.wikimedia.org", "upload.wikimedia.org", "wikipedia.org"}

# Пороги: выше — «проверено», между — «требует проверки», ниже — отклоняем.
VERIFIED_THRESHOLD = 0.62
REVIEW_THRESHOLD = 0.38

# Дальше этого расстояния от координат кампуса фото точно не про кампус.
MAX_CAMPUS_DISTANCE_M = 3000.0

# Снимок старше этого возраста помечаем как возможно устаревший (п.5 ТЗ).
STALE_AFTER_YEARS = 5.0

_YEAR_RE = re.compile(r"(1[89]\d{2}|20[0-9]{2})")


def photo_age_years(date: str | None) -> Optional[float]:
    """Возраст снимка в годах по дате из метаданных. None, если даты нет."""
    if not date:
        return None
    m = _YEAR_RE.search(date)
    if not m:
        return None
    year = int(m.group(1))
    now = dt.datetime.now(dt.timezone.utc).year
    if year > now:
        return None
    return float(now - year)


def metadata_blob(photo: Photo) -> str:
    """Весь текст, который Commons знает о файле, — вход для классификатора и улик."""
    parts = [photo.title.replace("_", " "), photo.description or "", *photo.commons_categories]
    return " ".join(p for p in parts if p)


def haversine_m(a: Coordinates, b: Coordinates) -> float:
    """Расстояние между точками на сфере, метры."""
    r = 6371008.8
    p1, p2 = math.radians(a.lat), math.radians(b.lat)
    dp = p2 - p1
    dl = math.radians(b.lon - a.lon)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def domain_of(url: str | None) -> Optional[str]:
    if not url:
        return None
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host or None


def _registrable(host: str) -> str:
    parts = host.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def domain_trust(url: str | None, official_site: str | None = None) -> tuple[float, str]:
    """Доверие к домену: официальный сайт > Commons > СМИ > неизвестный; сток = 0."""
    host = domain_of(url)
    if not host:
        return 0.2, "источник без домена"

    official_host = domain_of(official_site)
    if official_host and (host == official_host or host.endswith("." + official_host)):
        return 1.0, f"официальный сайт вуза ({host})"

    if _registrable(host) in STOCK_DOMAINS or host in STOCK_DOMAINS:
        return 0.0, f"стоковый фотобанк ({host})"

    if host in WIKIMEDIA_DOMAINS or host.endswith(".wikimedia.org") or host.endswith(".wikipedia.org"):
        return 0.8, f"Wikimedia Commons ({host})"

    if host.endswith(".edu") or ".edu." in host or host.endswith(".ac.uk") or ".ac." in host:
        return 0.75, f"образовательный домен ({host})"

    if host.endswith(".gov") or ".gov." in host or host.endswith(".gob"):
        return 0.7, f"государственный домен ({host})"

    return 0.3, f"неизвестный домен ({host})"


def score_photo(
    photo: Photo,
    campus: Coordinates | None,
    official_site: str | None,
    university_names: Iterable[str] = (),
) -> Photo:
    """Считает Confidence Score и заполняет разбор улик."""
    ev = Evidence(
        source_count=max(photo.evidence.source_count, len(photo.source_kinds), 1),
        has_license=bool(photo.license),
        license_name=photo.license,
        classifier_confidence=photo.evidence.classifier_confidence,
    )
    signals: list[EvidenceSignal] = []

    # 1. Геотег
    if photo.coordinates and campus:
        dist = haversine_m(photo.coordinates, campus)
        ev.geo_distance_m = round(dist, 1)
        value = max(0.0, 1.0 - dist / MAX_CAMPUS_DISTANCE_M)
        signals.append(
            EvidenceSignal(
                key="geo",
                label="Геотег",
                value=round(value, 3),
                weight=0.30,
                detail=f"{dist:,.0f} м до координат кампуса".replace(",", " "),
            )
        )
        if dist > MAX_CAMPUS_DISTANCE_M and photo.reject_reason is None:
            photo.reject_reason = RejectReason.TOO_FAR
            photo.reject_detail = f"Геотег в {dist / 1000:.1f} км от кампуса"
    elif campus:
        ev.notes.append("У фото нет геотега — сигнал расстояния не учитывался")

    # 2. Доверие к домену источника
    trust, trust_detail = domain_trust(photo.source_page_url, official_site)
    ev.domain = domain_of(photo.source_page_url)
    ev.domain_trust = trust
    signals.append(
        EvidenceSignal(
            key="domain", label="Источник", value=trust, weight=0.25, detail=trust_detail
        )
    )
    if trust == 0.0 and photo.reject_reason is None:
        photo.reject_reason = RejectReason.STOCK_DOMAIN
        photo.reject_detail = trust_detail

    # 3. Принадлежность к официальной категории вуза в Commons
    in_category = SourceKind.COMMONS_CATEGORY in photo.source_kinds
    by_name = SourceKind.COMMONS_SEARCH in photo.source_kinds
    if in_category:
        link_value, link_detail = 1.0, "файл лежит в категории Commons самого вуза"
    elif by_name:
        link_value, link_detail = 0.6, "файл найден поиском по названию вуза"
    else:
        link_value, link_detail = 0.35, "файл найден только по геопоиску рядом с кампусом"
    signals.append(
        EvidenceSignal(
            key="category",
            label="Привязка к вузу",
            value=link_value,
            weight=0.25,
            detail=link_detail,
        )
    )

    # 4. Название вуза в метаданных файла (имя, подпись, категории Commons)
    blob = metadata_blob(photo)
    mentions = mentions_university(blob, university_names)
    ev.name_mentions = mentions
    signals.append(
        EvidenceSignal(
            key="metadata",
            label="Вуз в метаданных",
            value=1.0 if mentions else 0.25,
            weight=0.15,
            detail=(
                f"название вуза найдено в метаданных: {', '.join(mentions[:2])}"
                if mentions
                else "название вуза в имени файла, подписи и категориях не встречается"
            ),
        )
    )

    # 5. Свежесть снимка
    age = photo_age_years(photo.date)
    ev.age_years = age
    if age is not None:
        photo.stale = age > STALE_AFTER_YEARS
        signals.append(
            EvidenceSignal(
                key="freshness",
                label="Свежесть",
                value=round(max(0.0, 1.0 - max(0.0, age - STALE_AFTER_YEARS) / 15.0), 3),
                weight=0.05,
                detail=(
                    f"снимку ~{age:.0f} лет — может быть устаревшим"
                    if photo.stale
                    else f"снимку ~{age:.0f} лет"
                ),
            )
        )
    else:
        ev.notes.append("У файла нет даты — свежесть не оценивалась")

    # 6. Повтор в нескольких источниках
    n = max(1, ev.source_count)
    signals.append(
        EvidenceSignal(
            key="sources",
            label="Повтор в источниках",
            value=1.0 if n >= 2 else 0.35,
            weight=0.10,
            detail=f"найдено в {n} источник(ах)",
        )
    )

    # 7. Классификатор — участвует, только когда реально посчитан
    if ev.classifier_confidence is not None:
        source = "по метаданным" if photo.category_source == "metadata" else "CLIP"
        terms = f" (по словам: {', '.join(photo.category_terms[:3])})" if photo.category_terms else ""
        signals.append(
            EvidenceSignal(
                key="classifier",
                label="Классификатор",
                value=round(ev.classifier_confidence, 3),
                weight=0.20,
                detail=(
                f"категория «{CATEGORY_LABELS.get(photo.category, photo.category.value)}» "
                f"определена {source}{terms}"
            ),
            )
        )
    else:
        ev.notes.append("Категорию определить не удалось — сигнал классификатора не учитывался")

    if photo.category is PhotoCategory.JUNK and photo.reject_reason is None:
        photo.reject_reason = RejectReason.JUNK_CLASS
        photo.reject_detail = (
            "Похоже на логотип/схему/документ, а не на фото кампуса"
            + (f" (по словам: {', '.join(photo.category_terms[:3])})" if photo.category_terms else "")
        )

    total_weight = sum(s.weight for s in signals) or 1.0
    score = sum(s.value * s.weight for s in signals) / total_weight

    if not photo.license and SourceKind.OFFICIAL_SITE in photo.source_kinds:
        ev.notes.append(
            "Снимок с официального сайта вуза: лицензия не указана, права принадлежат вузу"
        )

    ev.signals = signals
    photo.evidence = ev
    photo.confidence = round(score, 3)

    if photo.reject_reason is None and score < REVIEW_THRESHOLD:
        # Разделяем «слабые улики вообще» и «скорее всего это другой вуз»:
        # жюри должно видеть внятную причину, а не общее «низкий балл».
        wrong_university = not mentions and not (
            SourceKind.COMMONS_CATEGORY in photo.source_kinds
            or SourceKind.COMMONS_SEARCH in photo.source_kinds
        )
        if wrong_university:
            photo.reject_reason = RejectReason.NOT_THIS_UNIVERSITY
            photo.reject_detail = (
                f"Ничто не связывает фото с этим вузом: найдено только по геопоиску, "
                f"названия вуза в метаданных нет (балл {score:.2f})"
            )
        else:
            photo.reject_reason = RejectReason.LOW_CONFIDENCE
            photo.reject_detail = f"Низкий Confidence Score ({score:.2f})"
    return photo


def bucket(photo: Photo) -> str:
    """Куда фото попадёт в UI: verified / needs_review / rejected."""
    if photo.reject_reason is not None:
        return "rejected"
    return "verified" if photo.confidence >= VERIFIED_THRESHOLD else "needs_review"
