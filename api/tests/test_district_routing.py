"""Район и логистика: считаем только то, что отмечено на карте."""
import httpx
import pytest

from app.models import Coordinates
from app.services import osm, routing

OVERPASS = "https://overpass-api.de/api/interpreter"
OSRM = "https://router.project-osrm.org"

CAMPUS = Coordinates(lat=43.236, lon=76.929)
DORM = Coordinates(lat=43.238, lon=76.930)
CITY = Coordinates(lat=43.250, lon=76.945)

DISTRICT_ELEMENTS = [
    {"type": "way", "id": 1, "tags": {"highway": "residential", "lit": "yes"}},
    {"type": "way", "id": 2, "tags": {"highway": "footway", "lit": "yes"}},
    {"type": "way", "id": 3, "tags": {"highway": "residential", "lit": "no"}},
    {"type": "way", "id": 4, "tags": {"highway": "service"}},          # тега lit нет
    {"type": "way", "id": 5, "tags": {"highway": "residential"}},      # тега lit нет
    {"type": "node", "id": 6, "lat": 43.2361, "lon": 76.9291, "tags": {"highway": "street_lamp"}},
    {"type": "node", "id": 7, "lat": 43.2362, "lon": 76.9292, "tags": {"highway": "street_lamp"}},
    {"type": "node", "id": 8, "lat": 43.2363, "lon": 76.9293, "tags": {"highway": "crossing"}},
    {
        "type": "node",
        "id": 9,
        "lat": 43.2370,
        "lon": 76.9300,
        "tags": {"amenity": "police", "name": "УВД Бостандыкского района"},
    },
    {
        "type": "node",
        "id": 10,
        "lat": 43.2500,
        "lon": 76.9600,  # далеко — в ближайшие не попадёт
        "tags": {"amenity": "police", "name": "Дальний участок"},
    },
]


def test_district_counts_only_what_is_mapped():
    d = osm.parse_district(DISTRICT_ELEMENTS, CAMPUS, radius=1200)

    assert d.streets_total == 5
    assert d.streets_lit == 2
    assert d.streets_unlit == 1
    assert d.streets_without_lit_tag == 2
    # Доля считается от улиц С ТЕГОМ (2 из 3), а не от всех пяти.
    assert d.lit_share_percent == 67
    assert d.street_lamps == 2
    assert d.crossings == 1
    assert d.police is not None and d.police.name.startswith("УВД")


def test_district_has_no_safety_score():
    """Сводной оценки безопасности в ответе быть не должно — её нельзя честно посчитать."""
    d = osm.parse_district(DISTRICT_ELEMENTS, CAMPUS, radius=1200)
    fields = set(d.model_dump().keys())
    assert not {f for f in fields if "score" in f or "safe" in f or "rating" in f}


def test_district_without_lit_tags_reports_no_share():
    d = osm.parse_district(
        [{"type": "way", "id": 1, "tags": {"highway": "residential"}}], CAMPUS, radius=1200
    )
    assert d.lit_share_percent is None
    assert d.streets_without_lit_tag == 1


async def test_district_failure_is_marked(api_mock):
    api_mock.post(OVERPASS).mock(return_value=httpx.Response(429, text="too many requests"))
    d = await osm.fetch_district(CAMPUS)
    assert d is not None and d.available is False and d.error


async def test_osrm_leg_uses_real_route(api_mock):
    api_mock.get(url__startswith=f"{OSRM}/route/v1/driving/").mock(
        return_value=httpx.Response(
            200, json={"routes": [{"distance": 5400.0, "duration": 900.0}]}
        )
    )
    leg = await routing.driving_leg("city_drive", "До кампуса", "Алматы", "КБТУ", CITY, CAMPUS)

    assert leg.mode == "driving"
    assert leg.distance_m == 5400
    assert leg.minutes == 15
    assert "OSRM" in leg.note


async def test_osrm_failure_falls_back_to_straight_line(api_mock):
    api_mock.get(url__startswith=f"{OSRM}/route/v1/driving/").mock(
        return_value=httpx.Response(502, text="bad gateway")
    )
    leg = await routing.driving_leg("city_drive", "До кампуса", "Алматы", "КБТУ", CITY, CAMPUS)

    assert leg.mode == "straight"
    assert "не ответил" in leg.note
    assert leg.distance_m > 0


async def test_walking_leg_is_always_marked_as_estimate():
    """Пешеходного профиля у публичного OSRM нет, поэтому пеший участок — оценка."""
    leg = routing.straight_leg("dorm_walk", "Пешком", "Общежитие", "КБТУ", DORM, CAMPUS)
    assert leg.mode == "straight"
    assert "по прямой" in leg.note


async def test_logistics_without_dorm_and_city_says_why():
    result = await routing.build_logistics(CAMPUS, "КБТУ", None, None, None)
    assert result is not None
    assert result.legs == []
    assert result.error and "Wikidata" in result.error
