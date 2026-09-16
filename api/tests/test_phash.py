"""pHash-дедупликация на настоящих изображениях, сгенерированных на лету."""
import io

import httpx
import pytest
from PIL import Image, ImageDraw

from app.models import Coordinates, Photo, RejectReason, SourceKind
from app.services import dedup, phash


def make_image(seed: int, size: tuple[int, int] = (640, 480)) -> bytes:
    """Одна и та же сцена, отмасштабированная под нужный размер.

    Рисуем всегда на холсте 640×480 и уменьшаем: иначе при рисовании по
    абсолютным координатам меньший холст давал бы другую картинку, а не
    уменьшенную копию — и тест проверял бы не то.
    """
    base = (640, 480)
    img = Image.new("RGB", base, (18 + seed * 7 % 200, 40, 90))
    draw = ImageDraw.Draw(img)
    for i in range(6):
        x = 12 + i * 95 + seed * 9
        draw.rectangle([x, 120 + (i * seed) % 80, x + 62, 420], fill=(210, 180 - i * 12, 60 + seed))
    draw.ellipse([80 + seed, 20, 240 + seed, 140], fill=(240, 240, 250))
    if size != base:
        img = img.resize(size, Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=88)
    return buf.getvalue()


def photo(pid: str, url: str, *, width=1600, height=1200, kinds=None) -> Photo:
    return Photo(
        id=pid,
        title=pid,
        url=url,
        thumb_url=url,
        source_page_url=f"https://commons.wikimedia.org/wiki/File:{pid}",
        source_kinds=kinds or [SourceKind.COMMONS_CATEGORY],
        width=width,
        height=height,
        license="CC BY-SA 4.0",
    )


@pytest.fixture
def images(api_mock):
    """Один и тот же кадр в двух размерах + другой кадр."""
    same_big = make_image(1, (640, 480))
    same_small = make_image(1, (320, 240))
    different = make_image(9, (640, 480))

    api_mock.get("https://img.test/a.jpg").mock(
        return_value=httpx.Response(200, content=same_big, headers={"content-type": "image/jpeg"})
    )
    api_mock.get("https://img.test/b.jpg").mock(
        return_value=httpx.Response(200, content=same_small, headers={"content-type": "image/jpeg"})
    )
    api_mock.get("https://img.test/c.jpg").mock(
        return_value=httpx.Response(200, content=different, headers={"content-type": "image/jpeg"})
    )
    api_mock.get("https://img.test/broken.jpg").mock(return_value=httpx.Response(404))
    return api_mock


async def test_same_scene_in_two_sizes_is_collapsed(images):
    photos = [
        photo("a.jpg", "https://img.test/a.jpg"),
        photo("b.jpg", "https://img.test/b.jpg", width=320, height=240),
        photo("c.jpg", "https://img.test/c.jpg"),
    ]
    kept, dups = await dedup.perceptual_dedupe(photos)

    assert len(dups) == 1, "одинаковый кадр в двух размерах — один дубль"
    assert dups[0].reject_reason is RejectReason.DUPLICATE
    assert "pHash" in dups[0].reject_detail
    assert {p.id for p in kept} == {"a.jpg", "c.jpg"}, "разные кадры остаются оба"


async def test_bigger_version_wins(images):
    photos = [
        photo("b.jpg", "https://img.test/b.jpg", width=320, height=240),
        photo("a.jpg", "https://img.test/a.jpg", width=1600, height=1200),
    ]
    kept, dups = await dedup.perceptual_dedupe(photos)
    assert [p.id for p in kept] == ["a.jpg"], "оставляем версию большего разрешения"
    assert dups[0].id == "b.jpg"
    assert dups[0].duplicate_of == "a.jpg"


async def test_duplicate_adds_source_to_the_keeper(images):
    photos = [
        photo("a.jpg", "https://img.test/a.jpg", kinds=[SourceKind.COMMONS_CATEGORY]),
        photo("b.jpg", "https://img.test/b.jpg", width=320, height=240,
              kinds=[SourceKind.COMMONS_SEARCH]),
    ]
    kept, _ = await dedup.perceptual_dedupe(photos)
    keeper = kept[0]
    # Тот же кадр из второго источника — это подтверждение, а не потеря.
    assert set(keeper.source_kinds) == {SourceKind.COMMONS_CATEGORY, SourceKind.COMMONS_SEARCH}
    assert keeper.evidence.source_count == 2


async def test_undownloadable_photo_is_kept_not_dropped(images):
    photos = [
        photo("a.jpg", "https://img.test/a.jpg"),
        photo("broken.jpg", "https://img.test/broken.jpg"),
    ]
    kept, dups = await dedup.perceptual_dedupe(photos)
    # Не смогли посчитать хеш — это не повод считать фото дублем.
    assert {p.id for p in kept} == {"a.jpg", "broken.jpg"}
    assert dups == []


def test_hamming_and_threshold():
    assert phash.hamming("0000000000000000", "0000000000000000") == 0
    assert phash.hamming("0000000000000000", "000000000000000f") == 4
    assert phash.DEFAULT_THRESHOLD < 64


def test_thumb_url_requests_small_version():
    p = photo("x.jpg", "https://upload.wikimedia.org/wikipedia/commons/a/ab/X.jpg")
    p.thumb_url = "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/X.jpg/640px-X.jpg"
    assert phash._thumb_url(p, 240).endswith("/240px-X.jpg")


def test_quality_prefers_trusted_source():
    weak = photo("w.jpg", "https://img.test/a.jpg", kinds=[SourceKind.COMMONS_GEOSEARCH])
    strong = photo("s.jpg", "https://img.test/a.jpg", kinds=[SourceKind.COMMONS_CATEGORY])
    strong.coordinates = Coordinates(lat=1, lon=1)
    assert phash._quality(strong) > phash._quality(weak)
