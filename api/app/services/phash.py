"""Шаг 4 ТЗ: перцептивная дедупликация по pHash.

Точная дедупликация ловит только один и тот же файл Commons. Одно и то же
здание, загруженное двумя людьми (или та же фотография в другом разрешении
и с другим именем), остаётся двумя записями. pHash сравнивает изображения,
а не имена файлов.

Считаем по миниатюрам: скачивать оригиналы на 5 МБ ради 64-битного хеша
незачем, а бюджет у всего профиля — 25 секунд.
"""
from __future__ import annotations

import asyncio
import io
import logging
from typing import Optional

from app.models import Photo, RejectReason, SourceKind
from app.services.http import get_client

log = logging.getLogger(__name__)

# Расстояние Хэмминга между 64-битными хешами. 0 — пиксельно одинаковые,
# ≤6 — та же сцена в другом размере или с лёгкой обработкой.
DEFAULT_THRESHOLD = 6

# Дальше картинки уже разные, а качать больше — тратить бюджет.
MAX_DOWNLOADS = 120
DOWNLOAD_CONCURRENCY = 16
PER_IMAGE_TIMEOUT = 4.0


def _thumb_url(photo: Photo, width: int = 240) -> str:
    """Миниатюра Commons нужного размера, если её можно попросить."""
    url = photo.thumb_url or photo.url
    # Commons отдаёт произвольную ширину через сегмент /NNNpx- в имени.
    if "/thumb/" in url and "px-" in url:
        head, _, tail = url.rpartition("/")
        _, _, name = tail.partition("px-")
        return f"{head}/{width}px-{name}"
    return url


async def _fetch_hash(photo: Photo, semaphore: asyncio.Semaphore) -> Optional[str]:
    import imagehash
    from PIL import Image

    async with semaphore:
        try:
            client = await get_client()
            response = await client.get(_thumb_url(photo), timeout=PER_IMAGE_TIMEOUT)
            response.raise_for_status()
            with Image.open(io.BytesIO(response.content)) as image:
                # Считаем в оттенках серого: цветокоррекция не должна
                # превращать одно и то же фото в два разных.
                return str(imagehash.phash(image.convert("L")))
        except Exception as exc:  # noqa: BLE001 — одна картинка не должна ронять профиль
            log.debug("pHash для %s не посчитан: %s", photo.id, exc)
            return None


async def compute_hashes(photos: list[Photo], limit: int = MAX_DOWNLOADS) -> int:
    """Проставляет photo.phash. Возвращает, для скольких получилось."""
    targets = [p for p in photos if p.reject_reason is None and not p.phash][:limit]
    if not targets:
        return 0

    semaphore = asyncio.Semaphore(DOWNLOAD_CONCURRENCY)
    hashes = await asyncio.gather(
        *(_fetch_hash(p, semaphore) for p in targets), return_exceptions=True
    )

    done = 0
    for photo, result in zip(targets, hashes):
        if isinstance(result, str):
            photo.phash = result
            done += 1
    return done


def hamming(a: str, b: str) -> int:
    """Расстояние между двумя hex-представлениями pHash."""
    return bin(int(a, 16) ^ int(b, 16)).count("1")


def _quality(photo: Photo) -> tuple[int, int, int]:
    """Кого оставить из группы: больше пикселей, надёжнее источник, есть геотег."""
    pixels = (photo.width or 0) * (photo.height or 0)
    trusted = 1 if SourceKind.COMMONS_CATEGORY in photo.source_kinds else 0
    geo = 1 if photo.coordinates else 0
    return (trusted, pixels, geo)


def group_duplicates(
    photos: list[Photo], threshold: int = DEFAULT_THRESHOLD
) -> tuple[list[Photo], list[Photo]]:
    """Схлопывает похожие снимки. Возвращает (оставленные, дубли)."""
    hashed = [p for p in photos if p.phash]
    untouched = [p for p in photos if not p.phash]

    # Лучшие — первыми, тогда именно они становятся представителями групп.
    hashed.sort(key=_quality, reverse=True)

    keepers: list[Photo] = []
    duplicates: list[Photo] = []

    for photo in hashed:
        twin = next(
            (k for k in keepers if hamming(k.phash, photo.phash) <= threshold),  # type: ignore[arg-type]
            None,
        )
        if twin is None:
            keepers.append(photo)
            continue

        photo.duplicate_of = twin.id
        photo.reject_reason = RejectReason.DUPLICATE
        photo.reject_detail = f"Визуальный дубликат снимка {twin.title} (pHash)"
        duplicates.append(photo)

        # Дубликат в другом источнике — это подтверждение, а не потеря.
        for kind in photo.source_kinds:
            if kind not in twin.source_kinds:
                twin.source_kinds.append(kind)
        twin.evidence.source_count = max(
            twin.evidence.source_count, len(twin.source_kinds)
        )

    return [*keepers, *untouched], duplicates
