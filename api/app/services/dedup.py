"""Шаг 4 ТЗ: дедупликация.

Сейчас работает точная дедупликация (один и тот же файл, найденный разными
сборщиками) — она же даёт улику «повтор в нескольких источниках».
Перцептивный pHash (imagehash) и сравнение CLIP-эмбеддингов подключаются
в `perceptual_dedupe` — точка расширения намеренно оставлена явной.
"""
from __future__ import annotations

from app.models import Photo, RejectReason


def _key(photo: Photo) -> str:
    return photo.id


def exact_dedupe(photos: list[Photo]) -> tuple[list[Photo], list[Photo]]:
    """Схлопывает одинаковые файлы, сливая источники. Возвращает (уникальные, дубли)."""
    unique: dict[str, Photo] = {}
    duplicates: list[Photo] = []

    for photo in photos:
        key = _key(photo)
        keeper = unique.get(key)
        if keeper is None:
            photo.evidence.source_count = max(1, len(photo.source_kinds))
            unique[key] = photo
            continue

        for kind in photo.source_kinds:
            if kind not in keeper.source_kinds:
                keeper.source_kinds.append(kind)
        keeper.evidence.source_count = max(
            keeper.evidence.source_count, len(keeper.source_kinds)
        )
        photo.duplicate_of = keeper.id
        photo.reject_reason = RejectReason.DUPLICATE
        photo.reject_detail = f"Дубликат файла {keeper.title}"
        duplicates.append(photo)

    return list(unique.values()), duplicates


def perceptual_dedupe(photos: list[Photo]) -> tuple[list[Photo], list[Photo]]:
    """Заглушка под pHash/CLIP (шаг 4-5).

    Пока честно ничего не делает: без скачивания пикселей посчитать pHash
    нельзя, а выдумывать хеши мы не будем.
    """
    return photos, []


def dedupe(photos: list[Photo]) -> tuple[list[Photo], list[Photo]]:
    unique, dups = exact_dedupe(photos)
    unique, perceptual_dups = perceptual_dedupe(unique)
    return unique, dups + perceptual_dups
