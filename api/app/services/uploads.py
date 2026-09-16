"""Фото от студентов и начисление бонусов.

Отдельно и намеренно: эти снимки НЕ попадают в проверенную галерею.
Весь смысл сервиса — фотографии с проверяемым источником и лицензией,
а у пользовательского снимка ни того, ни другого нет. Они живут своим
разделом и подписаны как непроверенные.

Приватность: из файла вычитывается геометка (полезная улика), после чего
изображение пересохраняется БЕЗ EXIF. Мы не храним ни модель камеры,
ни серийный номер, ни исходные координаты с точностью до метра.
"""
from __future__ import annotations

import asyncio
import io
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

log = logging.getLogger(__name__)

ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp"}
MAX_BYTES = 8 * 1024 * 1024
MIN_SIDE = 480
COINS_PER_PHOTO = 10

_lock = asyncio.Lock()


class UploadError(ValueError):
    """Файл не принят. Текст показывается пользователю как есть."""


def _exif_gps(image: Any) -> Optional[tuple[float, float]]:
    """Координаты из EXIF, если они есть. Возвращает (lat, lon)."""
    try:
        exif = image.getexif()
        gps = exif.get_ifd(0x8825)  # GPSInfo
        if not gps:
            return None

        def to_degrees(value: Any) -> float:
            d, m, s = (float(x) for x in value)
            return d + m / 60 + s / 3600

        lat = to_degrees(gps[2])
        lon = to_degrees(gps[4])
        if gps.get(1) == "S":
            lat = -lat
        if gps.get(3) == "W":
            lon = -lon
        return lat, lon
    except Exception:  # noqa: BLE001 — кривой EXIF не повод отклонять фото
        return None


class UploadStore:
    def __init__(self, directory: Path) -> None:
        self.dir = directory
        self.dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.dir / "index.json"

    def _read(self) -> list[dict[str, Any]]:
        if not self.index_path.exists():
            return []
        try:
            return json.loads(self.index_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            log.warning("индекс загрузок не прочитан: %s", exc)
            return []

    def _write(self, items: list[dict[str, Any]]) -> None:
        tmp = self.index_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(self.index_path)

    async def save(
        self,
        *,
        device_id: str,
        content: bytes,
        content_type: str,
        university_id: str | None = None,
        university_name: str | None = None,
        caption: str | None = None,
    ) -> dict[str, Any]:
        if content_type not in ALLOWED_MIME:
            raise UploadError("Принимаем только JPEG, PNG или WebP")
        if len(content) > MAX_BYTES:
            raise UploadError(f"Файл больше {MAX_BYTES // 1024 // 1024} МБ")

        from PIL import Image

        try:
            image = Image.open(io.BytesIO(content))
            image.load()
        except Exception as exc:  # noqa: BLE001
            raise UploadError("Не удалось прочитать изображение") from exc

        if min(image.size) < MIN_SIDE:
            raise UploadError(
                f"Слишком маленькое фото ({image.width}×{image.height}), нужно от {MIN_SIDE} px"
            )

        coords = _exif_gps(image)

        photo_id = uuid.uuid4().hex
        filename = f"{photo_id}.jpg"

        # Пересохраняем без EXIF: метаданные камеры и точные координаты
        # пользователю в общий доступ не нужны.
        buffer = io.BytesIO()
        image.convert("RGB").save(buffer, format="JPEG", quality=85, optimize=True)
        (self.dir / filename).write_bytes(buffer.getvalue())

        record = {
            "id": photo_id,
            "device_id": device_id,
            "filename": filename,
            "width": image.width,
            "height": image.height,
            "university_id": university_id,
            "university_name": university_name,
            "caption": (caption or "").strip()[:200] or None,
            "coordinates": {"lat": coords[0], "lon": coords[1]} if coords else None,
            "coins": COINS_PER_PHOTO,
            # Миллисекунды, а не секунды: два снимка, загруженных подряд,
            # иначе получали одинаковую метку и вставали в галерее как попало.
            "created_at": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        }

        async with _lock:
            items = self._read()
            items.append(record)
            self._write(items)
        return record

    async def list_for_device(self, device_id: str) -> list[dict[str, Any]]:
        async with _lock:
            items = self._read()
        # Порядок вставки — надёжная подстраховка на случай совпадения меток.
        mine = [(n, i) for n, i in enumerate(items) if i.get("device_id") == device_id]
        mine.sort(key=lambda pair: (pair[1].get("created_at", ""), pair[0]), reverse=True)
        return [i for _, i in mine]

    async def wallet(self, device_id: str) -> dict[str, int]:
        mine = await self.list_for_device(device_id)
        return {
            "photos": len(mine),
            "coins": sum(int(i.get("coins", 0)) for i in mine),
            "per_photo": COINS_PER_PHOTO,
        }

    def file_path(self, filename: str) -> Optional[Path]:
        """Путь к файлу с защитой от выхода за пределы каталога."""
        candidate = (self.dir / filename).resolve()
        if candidate.parent != self.dir.resolve() or not candidate.is_file():
            return None
        return candidate
