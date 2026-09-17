"""События вуза: группировка уже найденных фото по годам (идея команды).

Никаких новых источников: мы не знаем расписания мероприятий и не выдумываем
его. Берём фотографии, которые уже прошли проверку, ищем в их метаданных
признаки события и раскладываем по годам съёмки. Если таких фото нет —
так и пишем, а не показываем пустой «календарь».
"""
from __future__ import annotations

import re
from typing import Iterable

from app.models import EventGroup, Photo

# Слова, по которым фото похоже на снимок с события. Как и в классификаторе,
# на трёх языках: Commons подписывают по-разному.
EVENT_TERMS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Выпускной и вручение дипломов", (
        "graduation", "commencement", "diploma ceremony", "convocation",
        "выпускн", "вручение дипломов", "бітіру",
    )),
    ("Посвящение и начало года", (
        "freshman", "first-year", "orientation", "knowledge day", "opening ceremony",
        "посвящение", "первокурсник", "день знаний", "тұсаукесер",
    )),
    ("Конференции и хакатоны", (
        "conference", "hackathon", "symposium", "forum", "seminar", "workshop",
        "конференц", "хакатон", "форум", "симпозиум",
    )),
    ("Праздники и фестивали", (
        "festival", "concert", "celebration", "anniversary", "holiday", "parade",
        "фестивал", "концерт", "праздн", "юбилей", "мерекe", "мерей",
    )),
    ("Спортивные события", (
        "championship", "tournament", "match", "competition", "spartakiad",
        "чемпионат", "турнир", "матч", "соревнован", "спартакиад",
    )),
    ("День открытых дверей", (
        "open day", "open doors", "open house", "admission",
        "день открытых дверей", "абитуриент",
    )),
)

_YEAR_RE = re.compile(r"(19|20)\d{2}")


def _haystack(photo: Photo) -> str:
    parts = [photo.title, photo.description or "", *photo.commons_categories]
    return " ".join(parts).lower()


def photo_year(photo: Photo) -> int | None:
    """Год съёмки из даты файла. Без даты год не выдумываем."""
    if not photo.date:
        return None
    m = _YEAR_RE.search(photo.date)
    return int(m.group(0)) if m else None


def build_events(photos: Iterable[Photo]) -> list[EventGroup]:
    """Группы событий, новые сверху. Внутри группы — годы, по которым есть фото."""
    buckets: dict[str, tuple[list[str], set[int]]] = {}

    for photo in photos:
        text = _haystack(photo)
        for title, terms in EVENT_TERMS:
            matched = [t for t in terms if t in text]
            if not matched:
                continue
            photo_ids, years = buckets.setdefault(title, ([], set()))
            photo_ids.append(photo.id)
            year = photo_year(photo)
            if year is not None:
                years.add(year)
            break  # одно фото — одно событие, иначе счётчики врут

    out: list[EventGroup] = []
    for title, terms in EVENT_TERMS:
        if title not in buckets:
            continue
        photo_ids, years = buckets[title]
        out.append(
            EventGroup(
                title=title,
                photo_ids=photo_ids,
                count=len(photo_ids),
                years=sorted(years, reverse=True),
            )
        )
    out.sort(key=lambda g: g.count, reverse=True)
    return out
