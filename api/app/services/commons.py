"""Шаг 2 ТЗ: сборщик Wikimedia Commons — категория вуза (P373) + geosearch."""
from __future__ import annotations

import asyncio
import html
import logging
import re
from typing import Any, Iterable, Optional

from app.config import get_settings
from app.models import Coordinates, Photo, RejectReason, SourceKind
from app.services.cache import get_cache
from app.services.http import get_json

log = logging.getLogger(__name__)

_TAG_RE = re.compile(r"<[^>]+>")
# Форматы, которые не являются фотографией кампуса.
_NON_PHOTO_EXT = (".svg", ".pdf", ".djvu", ".ogg", ".ogv", ".webm", ".mid", ".xcf", ".stl")
_MIN_SIDE = 320  # меньше — для галереи бесполезно


def strip_html(value: str | None) -> Optional[str]:
    if not value:
        return None
    text = html.unescape(_TAG_RE.sub(" ", value))
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def file_id(title: str) -> str:
    """Стабильный id файла: 'File:Foo bar.jpg' -> 'foo_bar.jpg'."""
    name = title.split(":", 1)[-1] if title.lower().startswith("file:") else title
    return name.strip().replace(" ", "_").lower()


async def _api(params: dict[str, Any]) -> dict[str, Any]:
    s = get_settings()
    base = {"action": "query", "format": "json", "formatversion": 2}
    return await get_json(s.commons_api, {**base, **params})


async def category_files(category: str, depth: int | None = None, limit: int | None = None) -> list[str]:
    """Обход категории Commons вширь до заданной глубины. Возвращает File:-заголовки."""
    s = get_settings()
    depth = s.category_depth if depth is None else depth
    limit = s.max_files_per_source if limit is None else limit

    cat = category.strip()
    if not cat.lower().startswith("category:"):
        cat = f"Category:{cat}"

    files: list[str] = []
    seen_cats: set[str] = set()
    frontier = [cat]

    for level in range(depth + 1):
        if not frontier or len(files) >= limit:
            break
        next_frontier: list[str] = []
        batches = await asyncio.gather(
            *(_category_page(c, want_subcats=level < depth) for c in frontier),
            return_exceptions=True,
        )
        for res in batches:
            if isinstance(res, BaseException):
                log.warning("categorymembers failed: %s", res)
                continue
            page_files, subcats = res
            for f in page_files:
                if f not in files:
                    files.append(f)
            for sc in subcats:
                if sc not in seen_cats:
                    seen_cats.add(sc)
                    next_frontier.append(sc)
        frontier = next_frontier[:20]  # не взрываем обход на огромных деревьях

    return files[:limit]


async def _category_page(category: str, want_subcats: bool) -> tuple[list[str], list[str]]:
    cmtype = "file|subcat" if want_subcats else "file"
    data = await _api(
        {
            "list": "categorymembers",
            "cmtitle": category,
            "cmtype": cmtype,
            "cmlimit": 500,
        }
    )
    files: list[str] = []
    subcats: list[str] = []
    for m in data.get("query", {}).get("categorymembers", []) or []:
        title = m.get("title", "")
        if m.get("ns") == 6:
            files.append(title)
        elif m.get("ns") == 14:
            subcats.append(title)
    return files, subcats


async def geosearch_files(
    lat: float, lon: float, radius: int | None = None, limit: int | None = None
) -> list[str]:
    """Файлы Commons с геотегом в радиусе вокруг кампуса."""
    s = get_settings()
    radius = s.geosearch_radius if radius is None else radius
    limit = s.max_files_per_source if limit is None else limit
    data = await _api(
        {
            "list": "geosearch",
            "gscoord": f"{lat}|{lon}",
            "gsradius": max(10, min(radius, 10000)),  # API допускает 10..10000 м
            "gslimit": min(limit, 500),
            "gsnamespace": 6,
        }
    )
    return [g["title"] for g in data.get("query", {}).get("geosearch", []) or [] if g.get("title")]


async def image_info(titles: list[str]) -> dict[str, dict[str, Any]]:
    """Метаданные файлов: url, автор, лицензия, дата, геотег. Батчами по 50."""
    result: dict[str, dict[str, Any]] = {}
    batches = [titles[i : i + 50] for i in range(0, len(titles), 50)]
    responses = await asyncio.gather(
        *(
            _api(
                {
                    "titles": "|".join(batch),
                    "prop": "imageinfo|coordinates|categories",
                    "iiprop": "url|extmetadata|user|timestamp|mime|size|canonicaltitle",
                    "iiurlwidth": 640,
                    "iiextmetadatalanguage": "ru",
                    "colimit": "max",
                    "cllimit": "max",
                    "clshow": "!hidden",
                }
            )
            for batch in batches
        ),
        return_exceptions=True,
    )
    for res in responses:
        if isinstance(res, BaseException):
            log.warning("imageinfo batch failed: %s", res)
            continue
        for page in res.get("query", {}).get("pages", []) or []:
            title = page.get("title")
            if title:
                result[title] = page
    return result


def _extmeta(page: dict[str, Any], key: str) -> Optional[str]:
    info = (page.get("imageinfo") or [{}])[0]
    meta = info.get("extmetadata") or {}
    val = (meta.get(key) or {}).get("value")
    return strip_html(val) if isinstance(val, str) else None


def _categories(page: dict[str, Any]) -> list[str]:
    """Категории Commons, в которых лежит файл, — сырьё для классификатора."""
    out: list[str] = []
    for c in page.get("categories") or []:
        title = c.get("title") or ""
        if title.lower().startswith("category:"):
            title = title.split(":", 1)[1]
        if title:
            out.append(title)
    # extmetadata тоже отдаёт категории строкой через | — на случай, если prop не пришёл
    raw = _extmeta(page, "Categories")
    if raw:
        for part in raw.split("|"):
            part = part.strip()
            if part and part not in out:
                out.append(part)
    return out


def _coords(page: dict[str, Any]) -> Optional[Coordinates]:
    coords = page.get("coordinates") or []
    if coords:
        c = coords[0]
        if c.get("lat") is not None and c.get("lon") is not None:
            return Coordinates(lat=float(c["lat"]), lon=float(c["lon"]))
    lat = _extmeta(page, "GPSLatitude")
    lon = _extmeta(page, "GPSLongitude")
    try:
        if lat and lon:
            return Coordinates(lat=float(lat), lon=float(lon))
    except ValueError:
        pass
    return None


def page_to_photo(page: dict[str, Any], source: SourceKind) -> Optional[Photo]:
    """Превращаем ответ Commons в Photo. Возвращает None для явно нефотографий."""
    title = page.get("title")
    infos = page.get("imageinfo") or []
    if not title or not infos:
        return None
    info = infos[0]
    url = info.get("url")
    descr = info.get("descriptionurl") or f"https://commons.wikimedia.org/wiki/{title.replace(' ', '_')}"
    if not url:
        return None

    photo = Photo(
        id=file_id(title),
        title=title.split(":", 1)[-1],
        url=url,
        thumb_url=info.get("thumburl") or url,
        source_page_url=descr,
        source_kinds=[source],
        author=_extmeta(page, "Artist") or info.get("user"),
        license=_extmeta(page, "LicenseShortName") or _extmeta(page, "UsageTerms"),
        license_url=(info.get("extmetadata", {}).get("LicenseUrl", {}) or {}).get("value"),
        date=(_extmeta(page, "DateTimeOriginal") or info.get("timestamp") or "")[:25] or None,
        coordinates=_coords(page),
        description=_extmeta(page, "ImageDescription") or _extmeta(page, "ObjectName"),
        commons_categories=_categories(page),
        width=info.get("width"),
        height=info.get("height"),
        mime=info.get("mime"),
    )

    lower = url.lower()
    if lower.endswith(_NON_PHOTO_EXT) or not (photo.mime or "").startswith("image/"):
        photo.reject_reason = RejectReason.NOT_A_PHOTO
        photo.reject_detail = f"Тип файла {photo.mime or 'неизвестен'} — не фотография"
    elif (photo.width or 0) < _MIN_SIDE and (photo.height or 0) < _MIN_SIDE:
        photo.reject_reason = RejectReason.TOO_SMALL
        photo.reject_detail = f"Слишком маленькое изображение ({photo.width}×{photo.height})"
    elif not photo.license:
        photo.reject_reason = RejectReason.NO_LICENSE
        photo.reject_detail = "У файла не указана лицензия"

    photo.evidence.has_license = bool(photo.license)
    photo.evidence.license_name = photo.license
    return photo


async def collect(
    *,
    commons_category: str | None,
    coordinates: Coordinates | None,
    radius: int | None = None,
) -> list[Photo]:
    """Оба сборщика Commons параллельно, с кешем по ключу источника."""
    s = get_settings()
    if not s.cache_enabled:
        return await _collect_uncached(
            commons_category=commons_category, coordinates=coordinates, radius=radius
        )

    cache = get_cache()
    key = cache.key(
        "commons",
        commons_category or "-",
        f"{coordinates.lat:.4f},{coordinates.lon:.4f}" if coordinates else "-",
        radius or s.geosearch_radius,
        s.max_files_per_source,
        s.category_depth,
    )

    async def produce() -> list[dict[str, Any]]:
        photos = await _collect_uncached(
            commons_category=commons_category, coordinates=coordinates, radius=radius
        )
        return [p.model_dump(mode="json") for p in photos]

    raw = await cache.get_or_set(key, s.cache_ttl_photos, produce)
    return [Photo.model_validate(item) for item in raw]


async def _collect_uncached(
    *,
    commons_category: str | None,
    coordinates: Coordinates | None,
    radius: int | None = None,
) -> list[Photo]:
    tasks: list[asyncio.Task[tuple[SourceKind, list[str]]]] = []

    async def _cat() -> tuple[SourceKind, list[str]]:
        return SourceKind.COMMONS_CATEGORY, await category_files(commons_category or "")

    async def _geo() -> tuple[SourceKind, list[str]]:
        assert coordinates is not None
        return SourceKind.COMMONS_GEOSEARCH, await geosearch_files(
            coordinates.lat, coordinates.lon, radius
        )

    if commons_category:
        tasks.append(asyncio.create_task(_cat()))
    if coordinates:
        tasks.append(asyncio.create_task(_geo()))
    if not tasks:
        return []

    title_sources: dict[str, set[SourceKind]] = {}
    for res in await asyncio.gather(*tasks, return_exceptions=True):
        if isinstance(res, BaseException):
            log.warning("commons collector failed: %s", res)
            continue
        kind, titles = res
        for t in titles:
            title_sources.setdefault(t, set()).add(kind)

    if not title_sources:
        return []

    pages = await image_info(list(title_sources))
    photos: list[Photo] = []
    for title, page in pages.items():
        kinds = sorted(title_sources.get(title, {SourceKind.COMMONS_CATEGORY}), key=lambda k: k.value)
        photo = page_to_photo(page, kinds[0])
        if photo is None:
            continue
        photo.source_kinds = list(kinds)
        photos.append(photo)
    return photos


def unique_titles(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for i in items:
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out
