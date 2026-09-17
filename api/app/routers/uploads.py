"""Фото от студентов и кошелёк бонусов (пункты 7-8 пожеланий к продукту).

Аутентификации нет: пользователь опознаётся анонимным идентификатором
устройства, который фронтенд хранит у себя. Это осознанное упрощение —
и оно означает, что бонусы не защищены от накрутки, а очистка данных
браузера обнуляет историю. В интерфейсе об этом сказано прямо.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Optional

from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.config import get_settings
from app.models import UploadListResponse, UploadRecord, WalletResponse
from app.routers.auth import current_user
from app.services.uploads import UploadError, UploadStore

router = APIRouter(tags=["uploads"])

_DEVICE_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


@lru_cache
def _store() -> UploadStore:
    return UploadStore(Path(get_settings().upload_dir))


async def _owner(authorization: str | None, device_id: str | None) -> str:
    """Чьи это фото.

    Вошедший пользователь опознаётся по токену — тогда его снимки видны
    с любого устройства. Без входа остаётся анонимный идентификатор
    браузера, как было раньше.
    """
    user = await current_user(authorization)
    if user is not None:
        return f"user:{user['id']}"

    if not device_id or not _DEVICE_RE.match(device_id):
        raise HTTPException(
            status_code=400,
            detail="Войдите в аккаунт или передайте заголовок X-Device-Id",
        )
    return f"device:{device_id}"


def _to_model(record: dict) -> UploadRecord:
    return UploadRecord(
        id=record["id"],
        url=f"/api/uploads/{record['filename']}",
        width=record["width"],
        height=record["height"],
        caption=record.get("caption"),
        university_name=record.get("university_name"),
        has_geotag=bool(record.get("coordinates")),
        coins=int(record.get("coins", 0)),
        created_at=record["created_at"],
    )


@router.post("/uploads", response_model=UploadRecord, status_code=201)
async def upload_photo(
    file: Annotated[UploadFile, File(description="JPEG, PNG или WebP до 8 МБ")],
    x_device_id: Annotated[str | None, Header()] = None,
    authorization: Annotated[str | None, Header()] = None,
    university_id: Annotated[Optional[str], Form()] = None,
    university_name: Annotated[Optional[str], Form()] = None,
    caption: Annotated[Optional[str], Form()] = None,
) -> UploadRecord:
    owner = await _owner(authorization, x_device_id)
    content = await file.read()

    try:
        record = await _store().save(
            device_id=owner,
            content=content,
            content_type=file.content_type or "",
            university_id=university_id,
            university_name=university_name,
            caption=caption,
        )
    except UploadError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=503, detail=f"Не удалось сохранить файл: {exc}") from exc

    return _to_model(record)


@router.get("/uploads", response_model=UploadListResponse)
async def my_uploads(
    x_device_id: Annotated[str | None, Header()] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> UploadListResponse:
    owner = await _owner(authorization, x_device_id)
    records = await _store().list_for_device(owner)
    return UploadListResponse(items=[_to_model(r) for r in records])


@router.get("/wallet", response_model=WalletResponse)
async def wallet(
    x_device_id: Annotated[str | None, Header()] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> WalletResponse:
    owner = await _owner(authorization, x_device_id)
    return WalletResponse(**await _store().wallet(owner))


@router.get("/uploads/{filename}")
async def get_upload(filename: str) -> FileResponse:
    path = _store().file_path(filename)
    if path is None:
        raise HTTPException(status_code=404, detail="Файл не найден")
    return FileResponse(path, media_type="image/jpeg")
