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


# --- текст со страниц сайта (источник для описания кампуса) ---

RICH_PAGE = """
<html>
<head>
  <title>О кампусе — КБТУ</title>
  <meta name="description" content="Кампус университета в центре Алматы">
</head>
<body>
  <nav><a href="/">Главная</a><a href="/news">Новости</a></nav>
  <script>var analytics = "это не должно попасть в текст";</script>
  <h1>Кампус университета</h1>
  <p>Главный корпус расположен в центре Алматы и занимает историческое здание,
     построенное в середине прошлого века и отреставрированное в 2011 году.</p>
  <ul><li>Меню</li><li>Ещё</li></ul>
  <p>На территории работают библиотека с читальным залом на двести мест,
     лаборатории и спортивный комплекс с бассейном.</p>
  <footer>Все права защищены. Контакты и телефоны приёмной комиссии</footer>
</body></html>
"""


@pytest.fixture
def rich_site(api_mock):
    api_mock.get(f"{SITE}/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\nDisallow: /admin/\n")
    )
    api_mock.get(f"{SITE}/about/campus").mock(
        return_value=httpx.Response(200, text=RICH_PAGE, headers={"content-type": "text/html"})
    )
    api_mock.get(f"{SITE}/students/dormitory").mock(
        return_value=httpx.Response(200, text=DORM, headers={"content-type": "text/html"})
    )
    api_mock.get(f"{SITE}/").mock(
        return_value=httpx.Response(200, text=HOME, headers={"content-type": "text/html"})
    )
    return api_mock


async def test_collects_meaningful_text(rich_site):
    texts = await officialsite.collect_texts(SITE)
    campus = next(t for t in texts if "campus" in t.url)

    assert campus.title == "О кампусе — КБТУ"
    assert "Главный корпус расположен в центре Алматы" in campus.text
    assert "библиотека с читальным залом" in campus.text
    assert campus.url == f"{SITE}/about/campus"


async def test_scripts_menus_and_footers_are_not_text(rich_site):
    campus = next(t for t in await officialsite.collect_texts(SITE) if "campus" in t.url)

    assert "analytics" not in campus.text, "содержимое script — не текст страницы"
    assert "Новости" not in campus.text, "пункты меню не нужны"
    assert "Меню" not in campus.text
    assert "приёмной комиссии" not in campus.text, "подвал не описывает кампус"


async def test_short_pages_are_skipped(rich_site):
    texts = await officialsite.collect_texts(SITE)
    # У страницы общежитий только картинка и никакого текста.
    assert not any("dormitory" in t.url for t in texts)


async def test_text_is_capped_per_page(rich_site):
    for t in await officialsite.collect_texts(SITE):
        assert len(t.text) <= 900, "в модель не должна уезжать вся страница целиком"


async def test_unreachable_site_yields_no_text(api_mock):
    api_mock.get(f"{SITE}/robots.txt").mock(side_effect=httpx.ConnectError("down"))
    api_mock.get(f"{SITE}/").mock(side_effect=httpx.ConnectError("down"))
    assert await officialsite.collect_texts(SITE) == []
