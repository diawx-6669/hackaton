import httpx
import pytest

from app.models import RejectReason, SourceKind
from app.services import officialsite

SITE = "https://kbtu.edu.kz"

HOME = """
<html><head><meta property="og:image" content="/media/hero.jpg"></head>
<body>
  <img src="/img/logo.png" alt="логотип">
  <img src="/media/main-building.jpg" alt="Главный корпус" width="1600" height="900">
  <img src="/icons/arrow.svg" alt="">
  <a href="/about/campus">Кампус</a>
  <a href="/students/dormitory">Общежития</a>
  <a href="https://facebook.com/kbtu">Facebook</a>
</body></html>
"""

CAMPUS = """
<html><body>
  <img src="/media/yard.jpg" alt="Двор" width="1200" height="800">
  <img src="/media/tiny-thumb.jpg" alt="мини" width="80" height="60">
</body></html>
"""

DORM = """<html><body><img src="/media/dorm.jpg" alt="Общежитие"></body></html>"""


@pytest.fixture
def site(api_mock):
    api_mock.get(f"{SITE}/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\nDisallow: /admin/\n")
    )
    # Подстраницы регистрируем ДО главной: голый хост в respx совпадает
    # с любым путём на нём и иначе перехватил бы их все.
    for url, html in (
        (f"{SITE}/about/campus", CAMPUS),
        (f"{SITE}/students/dormitory", DORM),
        (f"{SITE}/", HOME),
    ):
        api_mock.get(url).mock(
            return_value=httpx.Response(200, text=html, headers={"content-type": "text/html"})
        )
    return api_mock


async def test_collects_photos_from_campus_pages(site):
    photos = await officialsite.collect(SITE, "KBTU")
    urls = {p.url for p in photos}

    assert f"{SITE}/media/main-building.jpg" in urls
    assert f"{SITE}/media/yard.jpg" in urls, "должен зайти на страницу про кампус"
    assert f"{SITE}/media/dorm.jpg" in urls, "и на страницу про общежития"
    assert f"{SITE}/media/hero.jpg" in urls, "og:image тоже фотография"


async def test_service_graphics_are_skipped(site):
    urls = {p.url for p in await officialsite.collect(SITE, "KBTU")}
    assert not any("logo" in u for u in urls), "логотип — не фото кампуса"
    assert not any(u.endswith(".svg") for u in urls), "svg-иконки не берём"


async def test_photos_are_marked_as_official_source_without_license(site):
    photos = await officialsite.collect(SITE, "KBTU")
    main = next(p for p in photos if p.url.endswith("main-building.jpg"))
    assert main.source_kinds == [SourceKind.OFFICIAL_SITE]
    assert main.source_page_url.startswith(SITE)
    # Лицензию не выдумываем.
    assert main.license is None
    assert main.title == "Главный корпус"


async def test_small_images_are_rejected_with_reason(site):
    photos = await officialsite.collect(SITE, "KBTU")
    tiny = next(p for p in photos if "tiny-thumb" in p.url)
    assert tiny.reject_reason is RejectReason.TOO_SMALL


async def test_external_links_are_not_followed(site):
    photos = await officialsite.collect(SITE, "KBTU")
    assert all(p.url.startswith(SITE) for p in photos), "чужие домены не обходим"


async def test_robots_disallow_stops_the_crawler(api_mock):
    api_mock.get(f"{SITE}/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\nDisallow: /\n")
    )
    api_mock.get(SITE).mock(return_value=httpx.Response(200, text=HOME))
    assert await officialsite.collect(SITE, "KBTU") == []


async def test_unreachable_site_returns_nothing(api_mock):
    api_mock.get(f"{SITE}/robots.txt").mock(side_effect=httpx.ConnectError("down"))
    api_mock.get(SITE).mock(side_effect=httpx.ConnectError("down"))
    assert await officialsite.collect(SITE, "KBTU") == []


async def test_empty_website_is_noop():
    assert await officialsite.collect("", "KBTU") == []
