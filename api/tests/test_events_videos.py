"""События и видео: только из того, что реально нашлось."""
import httpx
import pytest

from app.models import Photo, SourceKind
from app.services import commons, events

COMMONS_API = "https://commons.wikimedia.org/w/api.php"


def photo(pid: str, title: str, date: str | None = None, cats: list[str] | None = None) -> Photo:
    return Photo(
        id=pid,
        title=title,
        url=f"https://upload.wikimedia.org/{pid}.jpg",
        source_page_url=f"https://commons.wikimedia.org/wiki/File:{pid}.jpg",
        source_kinds=[SourceKind.COMMONS_CATEGORY],
        date=date,
        commons_categories=cats or [],
    )


def test_events_grouped_by_kind_and_year():
    groups = events.build_events([
        photo("a", "KBTU graduation ceremony 2019", "2019-06-20"),
        photo("b", "Выпускной КБТУ", "2021-06-25"),
        photo("c", "Hackathon at KBTU", "2023-04-01"),
        photo("d", "Обычный корпус", "2020-01-01"),
    ])
    by_title = {g.title: g for g in groups}

    assert by_title["Выпускной и вручение дипломов"].count == 2
    assert by_title["Выпускной и вручение дипломов"].years == [2021, 2019]
    assert by_title["Конференции и хакатоны"].count == 1
    # Фото без признаков события ни в одну группу не попало.
    assert sum(g.count for g in groups) == 3


def test_photo_counted_once_even_if_matches_two_events():
    groups = events.build_events([photo("a", "Graduation festival concert", "2022-05-01")])
    assert sum(g.count for g in groups) == 1


def test_photo_without_date_has_no_year():
    groups = events.build_events([photo("a", "Graduation ceremony", None)])
    assert groups[0].count == 1
    assert groups[0].years == []


def test_no_events_means_empty_list_not_invented_calendar():
    assert events.build_events([photo("a", "Главный корпус", "2020-01-01")]) == []


async def test_category_videos_returns_only_video_files(api_mock):
    def handler(request: httpx.Request) -> httpx.Response:
        params = request.url.params
        if params.get("list") == "categorymembers":
            return httpx.Response(200, json={"query": {"categorymembers": [
                {"title": "File:KBTU tour.webm", "ns": 6},
                {"title": "File:KBTU building.jpg", "ns": 6},
            ]}})
        return httpx.Response(200, json={"query": {"pages": [
            {
                "title": "File:KBTU tour.webm",
                "imageinfo": [{
                    "url": "https://upload.wikimedia.org/KBTU_tour.webm",
                    "descriptionurl": "https://commons.wikimedia.org/wiki/File:KBTU_tour.webm",
                    "mime": "video/webm",
                    "duration": 12.5,
                    "user": "Someone",
                    "extmetadata": {"LicenseShortName": {"value": "CC BY-SA 4.0"}},
                }],
            }
        ]}})

    api_mock.get(COMMONS_API).mock(side_effect=handler)
    videos = await commons.category_videos("Kazakh-British Technical University")

    assert len(videos) == 1
    assert videos[0]["mime"] == "video/webm"
    assert videos[0]["duration_s"] == 12
    assert videos[0]["license"] == "CC BY-SA 4.0"


async def test_no_videos_in_category_returns_empty(api_mock):
    api_mock.get(COMMONS_API).mock(
        return_value=httpx.Response(200, json={"query": {"categorymembers": [
            {"title": "File:Only a photo.jpg", "ns": 6}
        ]}})
    )
    assert await commons.category_videos("Whatever") == []
