"""Окружение кампуса: разбор ответа Overpass и поведение при его падении."""
import httpx
import pytest
import respx

from app.models import Coordinates
from app.services import osm

OVERPASS = "https://overpass-api.de/api/interpreter"

CAMPUS = Coordinates(lat=43.2359, lon=76.9455)

# 0.0009° широты ≈ 100 м, 0.009° ≈ 1 км — этого хватает, чтобы развести
# объекты «рядом» и «за радиусом».
ELEMENTS = [
    {
        "type": "node",
        "id": 1,
        "lat": 43.2366,
        "lon": 76.9455,
        "tags": {"highway": "bus_stop", "name": "КБТУ"},
    },
    {
        "type": "node",
        "id": 2,
        "lat": 43.2380,
        "lon": 76.9455,
        "tags": {"railway": "subway_entrance", "name": "Абая"},
    },
    {
        "type": "way",
        "id": 3,
        "center": {"lat": 43.2362, "lon": 76.9460},
        "tags": {"shop": "supermarket", "name": "Магнум"},
    },
    {
        "type": "node",
        "id": 4,
        "lat": 43.2361,
        "lon": 76.9450,
        "tags": {"amenity": "pharmacy"},  # без названия — такое в OSM обычное дело
    },
    {
        "type": "way",
        "id": 5,
        "center": {"lat": 43.2500, "lon": 76.9455},  # ~1.6 км — за радиусом
        "tags": {"leisure": "park", "name": "Далёкий парк"},
    },
    {
        "type": "node",
        "id": 6,
        "lat": 43.2360,
        "lon": 76.9456,
        "tags": {"name": "Без полезных тегов"},  # ни в одну группу не попадает
    },
]


def test_parse_groups_and_distances():
    groups = {g.key: g for g in osm.parse_elements(ELEMENTS, CAMPUS, radius=1200)}

    assert groups["transport"].count == 2
    assert groups["groceries"].count == 1
    assert groups["health"].count == 1

    # Объект за радиусом отброшен, парк остался пустой группой с объяснением.
    assert groups["green"].count == 0
    assert groups["green"].empty_reason

    # Ближайшие идут первыми.
    nearest = groups["transport"].nearest
    assert [p.name for p in nearest] == ["КБТУ", "Абая"]
    assert nearest[0].distance_m < nearest[1].distance_m
    assert nearest[0].walk_minutes >= 1
    assert nearest[0].osm_url == "https://www.openstreetmap.org/node/1"

    # Объект без имени не выбрасывается — он всё равно есть на местности.
    assert groups["health"].nearest[0].name == ""


def test_duplicate_elements_counted_once():
    groups = {g.key: g for g in osm.parse_elements(ELEMENTS + ELEMENTS, CAMPUS, radius=1200)}
    assert groups["transport"].count == 2


def test_element_without_coordinates_skipped():
    groups = {
        g.key: g
        for g in osm.parse_elements(
            [{"type": "way", "id": 9, "tags": {"amenity": "pharmacy"}}], CAMPUS, radius=1200
        )
    }
    assert groups["health"].count == 0


async def test_fetch_surroundings_reads_overpass(api_mock):
    api_mock.post(OVERPASS).mock(return_value=httpx.Response(200, json={"elements": ELEMENTS}))
    result = await osm.fetch_surroundings(CAMPUS)

    assert result is not None and result.available is True
    assert result.total == 4  # пятый за радиусом, шестой без тегов группы
    assert result.radius_m == osm.DEFAULT_RADIUS_M


async def test_overpass_failure_does_not_break_profile(api_mock):
    """Недоступный источник помечается, а не роняет ответ (п.2 ТЗ)."""
    api_mock.post(OVERPASS).mock(return_value=httpx.Response(504, text="gateway timeout"))
    result = await osm.fetch_surroundings(CAMPUS)

    assert result is not None
    assert result.available is False
    assert result.error and "Overpass" in result.error
    assert result.groups == []


async def test_no_coordinates_means_no_request(api_mock):
    route = api_mock.post(OVERPASS).mock(return_value=httpx.Response(200, json={"elements": []}))
    assert await osm.fetch_surroundings(None) is None
    assert not route.called
