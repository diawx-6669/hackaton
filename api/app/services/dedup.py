"""Шаг 4 ТЗ: дедупликация.

Два уровня. Точная — один и тот же файл Commons, найденный разными
сборщиками; она же даёт улику «повтор в нескольких источниках».
Перцептивная — pHash по миниатюрам: ловит ту же сцену, загруженную
другим человеком или в другом разрешении.

Сравнение CLIP-эмбеддингов (похожие, но не идентичные ракурсы) остаётся
следующим шагом — оно подключается там же, где считается pHash.
"""
from __future__ import annotations

from app.models import Photo, RejectReason
from app.services import phash as phash_service


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


async def perceptual_dedupe(
    photos: list[Photo], threshold: int | None = None
) -> tuple[list[Photo], list[Photo]]:
    """pHash по миниатюрам: одна сцена — одна карточка.

    Картинки, для которых хеш посчитать не удалось (сеть, битый файл),
    не выбрасываются: отсутствие хеша — не повод считать фото дублем.
    """
    await phash_service.compute_hashes(photos)
    return phash_service.group_duplicates(
        photos, threshold if threshold is not None else phash_service.DEFAULT_THRESHOLD
    )


async def dedupe(photos: list[Photo]) -> tuple[list[Photo], list[Photo]]:
    unique, dups = exact_dedupe(photos)
    unique, perceptual_dups = await perceptual_dedupe(unique)
    return unique, dups + perceptual_dups
