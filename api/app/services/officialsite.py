"""Шаг 2 ТЗ: картинки с официального сайта вуза.

Зачем это нужно, кроме галочки в ТЗ: сайт вуза — самый доверенный домен
(1.0 в уликах) и источник, независимый от Wikimedia. Один и тот же снимок,
найденный и там и там, получает улику «повтор в источниках».

Правила, которые соблюдаем:
- robots.txt читаем и подчиняемся;
- ходим только по страницам самого вуза, максимум на один уровень вглубь;
- лицензию НЕ придумываем: у снимков с сайта её нет, так и пишем.
"""
from __future__ import annotations

import asyncio
import logging
import re
from html.parser import HTMLParser
from typing import Optional
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

from app.config import get_settings
from app.models import Photo, RejectReason, SiteText, SourceKind
from app.services.cache import get_cache
from app.services.http import get_client

log = logging.getLogger(__name__)

# Страницы, на которых у вузов обычно живут фотографии кампуса.
PAGE_HINTS = (
    "campus", "about", "gallery", "photo", "dormitor", "hostel", "library",
    "sport", "student", "life", "facilities", "virtual", "tour", "infrastructure",
    "кампус", "о-универ", "об-универ", "общежит", "библиотек", "спорт",
    "студен", "галере", "фото", "инфраструктур",
)

# Служебная графика, которая фотографией кампуса не является.
JUNK_IN_URL = (
    "logo", "icon", "favicon", "sprite", "placeholder", "avatar", "banner",
    "button", "arrow", "bg-", "background", "pattern", "flag", "emblem",
    "герб", "логотип",
)

IMAGE_EXT = (".jpg", ".jpeg", ".png", ".webp")
MAX_PAGES = 5
MAX_IMAGES = 40
PAGE_TIMEOUT = 6.0


# Блоки, текст которых к описанию кампуса отношения не имеет.
SKIP_TAGS = {"script", "style", "nav", "footer", "header", "form", "noscript", "svg"}
TEXT_TAGS = {"p", "h1", "h2", "h3", "li"}
MIN_LINE = 60       # короче — это пункт меню, а не предложение
MAX_PAGE_CHARS = 900
MAX_TOTAL_PAGES = 4


class _TextExtractor(HTMLParser):
    """Собирает осмысленный текст: заголовки и абзацы, без меню и скриптов."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.description = ""
        self._chunks: list[str] = []
        self._skip_depth = 0
        self._capture = 0
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in SKIP_TAGS:
            self._skip_depth += 1
        elif tag == "title":
            self._in_title = True
        elif tag in TEXT_TAGS and not self._skip_depth:
            self._capture += 1
        elif tag == "meta":
            data = {k: (v or "") for k, v in attrs}
            if data.get("name") == "description" and data.get("content"):
                self.description = data["content"].strip()

    def handle_endtag(self, tag: str) -> None:
        if tag in SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1
        elif tag == "title":
            self._in_title = False
        elif tag in TEXT_TAGS and self._capture:
            self._capture -= 1
            self._chunks.append("\n")

    def handle_data(self, data: str) -> None:
        if self._in_title and not self.title:
            self.title = data.strip()
        elif self._capture and not self._skip_depth:
            self._chunks.append(data)

    @property
    def text(self) -> str:
        raw = "".join(self._chunks)
        lines = []
        seen: set[str] = set()
        for line in raw.split("\n"):
            cleaned = re.sub(r"\s+", " ", line).strip()
            if len(cleaned) >= MIN_LINE and cleaned not in seen:
                seen.add(cleaned)
                lines.append(cleaned)
        return " ".join(lines)[:MAX_PAGE_CHARS]


class _Extractor(HTMLParser):
    """Достаёт из страницы ссылки и картинки. Хватает stdlib, без bs4."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []
        self.images: list[tuple[str, Optional[int], Optional[int], str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        data = {k: (v or "") for k, v in attrs}
        if tag == "a" and data.get("href"):
            self.links.append(data["href"])
        elif tag == "img":
            src = data.get("src") or data.get("data-src") or ""
            if not src and data.get("srcset"):
                src = data["srcset"].split(",")[0].strip().split(" ")[0]
            if src:
                self.images.append(
                    (src, _to_int(data.get("width")), _to_int(data.get("height")),
                     data.get("alt", ""))
                )
        elif tag == "meta" and data.get("property") in ("og:image", "twitter:image"):
            if data.get("content"):
                self.images.append((data["content"], None, None, ""))


def _to_int(value: str | None) -> Optional[int]:
    try:
        return int(re.sub(r"\D", "", value or "")) or None
    except ValueError:
        return None


async def _robots(base: str) -> RobotFileParser:
    parser = RobotFileParser()
    parser.set_url(urljoin(base, "/robots.txt"))
    try:
        client = await get_client()
        response = await client.get(urljoin(base, "/robots.txt"), timeout=PAGE_TIMEOUT)
        if response.status_code == 200:
            parser.parse(response.text.splitlines())
        else:
            parser.parse([])  # нет robots.txt — значит запретов нет
    except Exception as exc:  # noqa: BLE001
        log.debug("robots.txt для %s не прочитан: %s", base, exc)
        parser.parse([])
    return parser


async def _fetch(url: str) -> Optional[str]:
    try:
        client = await get_client()
        response = await client.get(url, timeout=PAGE_TIMEOUT)
        response.raise_for_status()
        if "text/html" not in response.headers.get("content-type", ""):
            return None
        return response.text
    except Exception as exc:  # noqa: BLE001
        log.debug("страница %s не получена: %s", url, exc)
        return None


def _is_photo_url(url: str) -> bool:
    lowered = url.lower().split("?")[0]
    if not lowered.endswith(IMAGE_EXT):
        return False
    return not any(junk in lowered for junk in JUNK_IN_URL)


def _pick_pages(html: str, base: str, host: str) -> list[str]:
    parser = _Extractor()
    parser.feed(html)
    picked: list[str] = []
    for href in parser.links:
        absolute = urljoin(base, href)
        parsed = urlparse(absolute)
        if parsed.hostname != host or parsed.scheme not in ("http", "https"):
            continue
        if any(hint in absolute.lower() for hint in PAGE_HINTS) and absolute not in picked:
            picked.append(absolute)
        if len(picked) >= MAX_PAGES:
            break
    return picked


def _to_photos(html: str, page_url: str, host: str) -> list[Photo]:
    parser = _Extractor()
    parser.feed(html)
    photos: list[Photo] = []
    seen: set[str] = set()

    for src, width, height, alt in parser.images:
        url = urljoin(page_url, src)
        if url in seen or not _is_photo_url(url):
            continue
        seen.add(url)

        photo = Photo(
            id=f"site:{urlparse(url).path.rsplit('/', 1)[-1].lower()}",
            title=alt.strip() or urlparse(url).path.rsplit("/", 1)[-1],
            url=url,
            thumb_url=url,
            source_page_url=page_url,
            source_kinds=[SourceKind.OFFICIAL_SITE],
            author=host,
            # Лицензию не выдумываем: на сайтах вузов её обычно нет.
            license=None,
            width=width,
            height=height,
            mime="image/jpeg",
            description=alt.strip() or None,
        )
        # Слишком мелкое по атрибутам — иконка, а не фотография.
        if (width and width < 320) or (height and height < 240):
            photo.reject_reason = RejectReason.TOO_SMALL
            photo.reject_detail = f"Мелкое изображение на сайте ({width}×{height})"
        photos.append(photo)

        if len(photos) >= MAX_IMAGES:
            break
    return photos


async def _crawl(website: str) -> list[tuple[str, str]]:
    """Страницы сайта: главная плюс подходящие по смыслу. Результат кешируется,
    чтобы сбор фотографий и сбор текста не ходили на сайт по второму разу."""
    parsed = urlparse(website if "://" in website else f"https://{website}")
    host = parsed.hostname
    if not host:
        return []
    base = f"{parsed.scheme}://{host}"

    settings = get_settings()
    cache = get_cache()
    key = cache.key("site", base)

    async def produce() -> list[tuple[str, str]]:
        robots = await _robots(base)
        agent = "CampusLens"
        if not robots.can_fetch(agent, base):
            log.info("robots.txt запрещает обход %s", host)
            return []

        home = await _fetch(base)
        if not home:
            return []

        pages = [p for p in _pick_pages(home, base, host) if robots.can_fetch(agent, p)]
        fetched = await asyncio.gather(*(_fetch(p) for p in pages), return_exceptions=True)

        result = [(base, home)]
        for url, html in zip(pages, fetched):
            if isinstance(html, str):
                result.append((url, html))
        return result

    if not settings.cache_enabled:
        return await produce()
    return await cache.get_or_set(key, settings.cache_ttl_photos, produce)


async def collect_texts(website: str) -> list[SiteText]:
    """Текст со страниц о вузе — источник для описания кампуса (шаг 6 ТЗ)."""
    pages = await _crawl(website)
    texts: list[SiteText] = []

    for url, html in pages[:MAX_TOTAL_PAGES]:
        parser = _TextExtractor()
        try:
            parser.feed(html)
        except Exception as exc:  # noqa: BLE001 — кривая разметка не повод падать
            log.debug("текст со страницы %s не разобран: %s", url, exc)
            continue

        body = parser.text or parser.description
        if body and len(body) >= MIN_LINE:
            texts.append(SiteText(url=url, title=parser.title or url, text=body))
    return texts


async def collect(website: str, university_name: str = "") -> list[Photo]:
    """Фотографии со страниц о кампусе на официальном сайте вуза."""
    if not website:
        return []

    pages = await _crawl(website)
    if not pages:
        return []
    host = urlparse(pages[0][0]).hostname or ""

    photos: list[Photo] = []
    for page_url, html in pages:
        photos.extend(_to_photos(html, page_url, host))

    # Один и тот же файл на нескольких страницах — не повод его дублировать.
    unique: dict[str, Photo] = {}
    for photo in photos:
        unique.setdefault(photo.url, photo)
    return list(unique.values())[:MAX_IMAGES]
