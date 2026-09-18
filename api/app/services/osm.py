"""Окружение кампуса по данным OpenStreetMap (п.8 ТЗ: «жизнь в радиусе 15 минут»).

Всё, что здесь считается, берётся из ответа Overpass и расстояния до точки
кампуса. Ничего не достраивается: если объекта в OSM нет — мы пишем, что его
нет в OSM, а не что его нет в реальности.

Отдельно про инфраструктуру района. Мы считаем факты, отмеченные на карте:
сколько улиц помечено как освещённые, сколько фонарей и переходов, где
ближайший полицейский участок. Сводной «оценки безопасности» здесь нет и не
будет: она складывалась бы из данных, которых в OSM нет (охрана на входе,
реальная освещённость, ночная обстановка), и выглядела бы авторитетно, будучи
выдумкой. Про неполноту карты блок сообщает прямым текстом.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.config import get_settings
from app.models import (
    Coordinates,
    DistrictInfo,
    Surroundings,
    SurroundingGroup,
    SurroundingPlace,
)
from app.services.cache import get_cache
from app.services.evidence import haversine_m
from app.services.http import post_json

log = logging.getLogger(__name__)

# Скорость пешехода для оценки времени. 4.5 км/ч — спокойный шаг взрослого.
WALK_SPEED_M_PER_MIN = 75.0

# Радиус поиска: 15 минут пешком ≈ 1100 м по прямой. Берём с запасом.
DEFAULT_RADIUS_M = 1200

# Группы объектов: заголовок для интерфейса и фильтры Overpass.
# Порядок важен — в таком виде группы показываются на странице.
GROUPS: list[tuple[str, str, tuple[str, ...]]] = [
    ("transport", "Транспорт", (
        'node["highway"="bus_stop"]',
        'node["railway"="station"]',
        'node["railway"="subway_entrance"]',
        'node["railway"="tram_stop"]',
    )),
    ("food", "Еда", (
        'nwr["amenity"="cafe"]',
        'nwr["amenity"="fast_food"]',
        'nwr["amenity"="restaurant"]',
        'nwr["amenity"="canteen"]',
    )),
    ("groceries", "Продукты", (
        'nwr["shop"="supermarket"]',
        'nwr["shop"="convenience"]',
        'nwr["amenity"="marketplace"]',
    )),
    ("health", "Аптеки и медицина", (
        'nwr["amenity"="pharmacy"]',
        'nwr["amenity"="clinic"]',
        'nwr["amenity"="hospital"]',
    )),
    ("study", "Учёба рядом", (
        'nwr["amenity"="library"]',
        'nwr["amenity"="university"]',
        'nwr["amenity"="college"]',
    )),
    ("sports", "Спорт", (
        'nwr["leisure"="sports_centre"]',
        'nwr["leisure"="fitness_centre"]',
        'nwr["leisure"="stadium"]',
        'nwr["leisure"="swimming_pool"]',
    )),
    ("green", "Парки и зелень", (
        'nwr["leisure"="park"]',
        'nwr["leisure"="garden"]',
        'nwr["landuse"="forest"]',
    )),
    ("dorms", "Общежития", (
        'nwr["building"="dormitory"]',
        'nwr["amenity"="dormitory"]',
    )),
]


# Инфраструктура района. Считаем только штуки, а не «баллы»: сводный индекс
# безопасности по этим данным честно не выводится.
DISTRICT_FILTERS: tuple[str, ...] = (
    'way["highway"~"^(residential|living_street|pedestrian|footway|path|service|tertiary|secondary|primary|unclassified)$"]',
    'node["highway"="street_lamp"]',
    'node["highway"="crossing"]',
    'node["crossing"]',
    'nwr["amenity"="police"]',
    'nwr["emergency"="phone"]',
)


def _build_district_query(coords: Coordinates, radius: int) -> str:
    around = f"(around:{radius},{coords.lat},{coords.lon})"
    parts = [f"{f}{around};" for f in DISTRICT_FILTERS]
    return "[out:json][timeout:25];(" + "".join(parts) + ");out center tags;"


def _build_query(coords: Coordinates, radius: int) -> str:
    around = f"(around:{radius},{coords.lat},{coords.lon})"
    parts = [f"{f}{around};" for _, _, filters in GROUPS for f in filters]
    # out center — чтобы у линий и полигонов тоже была одна точка.
    return "[out:json][timeout:20];(" + "".join(parts) + ");out center tags;"


def _element_coords(el: dict[str, Any]) -> Coordinates | None:
    if "lat" in el and "lon" in el:
        return Coordinates(lat=float(el["lat"]), lon=float(el["lon"]))
    center = el.get("center")
    if center and "lat" in center and "lon" in center:
        return Coordinates(lat=float(center["lat"]), lon=float(center["lon"]))
    return None


def _parse_filter(f: str) -> tuple[str, str]:
    """'nwr["shop"="supermarket"]' → ("shop", "supermarket")."""
    tag = f[f.index('["') + 2 : f.index('"=')]
    value = f[f.index('"="') + 3 : f.rindex('"]')]
    return tag, value


# (тег, значение) → группа. Строится один раз из GROUPS, чтобы разбор ответа
# не занимался парсингом строк запроса на каждом объекте.
_TAG_TO_GROUP: dict[tuple[str, str], str] = {
    _parse_filter(f): key for key, _, filters in GROUPS for f in filters
}


def _group_of(tags: dict[str, str]) -> str | None:
    """Группа объекта. Порядок GROUPS решает, если тегов совпало несколько."""
    for (tag, value), key in _TAG_TO_GROUP.items():
        if tags.get(tag) == value:
            return key
    return None


def _walk_minutes(distance_m: float) -> int:
    return max(1, round(distance_m / WALK_SPEED_M_PER_MIN))


async def _overpass(query: str) -> dict[str, Any]:
    """Спрашиваем зеркала по очереди: первое ответившее и выигрывает.

    Публичные инстансы Overpass регулярно отвечают 429 под нагрузкой, и один
    адрес — это гарантированные пустые блоки в час пик.
    """
    s = get_settings()
    mirrors = s.overpass_mirrors
    last: Exception | None = None
    for url in mirrors:
        try:
            return await post_json(url, {"data": query}, retries=0, timeout=s.overpass_timeout)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 — пробуем следующее зеркало
            log.warning("overpass %s не ответил: %s", url, exc)
            last = exc
    raise last or RuntimeError("не задано ни одного адреса Overpass")


def parse_elements(
    elements: list[dict[str, Any]], campus: Coordinates, radius: int
) -> list[SurroundingGroup]:
    """Разбор ответа Overpass в группы. Вынесен отдельно — так его можно тестировать."""
    buckets: dict[str, list[SurroundingPlace]] = {key: [] for key, _, _ in GROUPS}
    seen: set[tuple[str, int]] = set()

    for el in elements:
        key = (el.get("type", ""), int(el.get("id", 0)))
        if key in seen:
            continue
        seen.add(key)

        tags = el.get("tags") or {}
        group = _group_of(tags)
        coords = _element_coords(el)
        if group is None or coords is None:
            continue

        distance = haversine_m(coords, campus)
        if distance > radius:
            continue

        buckets[group].append(
            SurroundingPlace(
                name=tags.get("name") or tags.get("name:ru") or "",
                distance_m=round(distance),
                walk_minutes=_walk_minutes(distance),
                osm_url=f"https://www.openstreetmap.org/{el.get('type')}/{el.get('id')}",
                coordinates=coords,
            )
        )

    out: list[SurroundingGroup] = []
    for key, title, _ in GROUPS:
        places = sorted(buckets[key], key=lambda p: p.distance_m)
        out.append(
            SurroundingGroup(
                key=key,
                title=title,
                count=len(places),
                # Показываем ближайшие — остальные только считаем.
                nearest=places[:3],
                empty_reason=None if places else f"в OSM в радиусе {radius} м ничего не отмечено",
            )
        )
    return out


async def fetch_surroundings(
    coords: Coordinates | None, radius: int = DEFAULT_RADIUS_M
) -> Surroundings | None:
    """Что есть вокруг кампуса. None — координат нет, значит и считать нечего."""
    if coords is None:
        return None

    s = get_settings()
    cache = get_cache()
    key = f"osm:v1:{coords.lat:.4f},{coords.lon:.4f}:{radius}"

    async def produce() -> Surroundings:
        data = await _overpass(_build_query(coords, radius))
        groups = parse_elements(data.get("elements") or [], coords, radius)
        return Surroundings(
            radius_m=radius,
            groups=groups,
            total=sum(g.count for g in groups),
            available=True,
        )

    try:
        return await cache.get_or_set(key, s.cache_ttl_resolve, produce)
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # noqa: BLE001 — недоступный источник не роняет профиль
        log.warning("overpass failed: %s", exc)
        return Surroundings(
            radius_m=radius,
            groups=[],
            total=0,
            available=False,
            error="OpenStreetMap (Overpass) не ответил — данные об окружении не собраны",
        )


def parse_district(
    elements: list[dict[str, Any]], campus: Coordinates, radius: int
) -> DistrictInfo:
    """Факты об инфраструктуре района. Никакого сводного балла — см. докстроку модуля."""
    lit_yes = 0
    lit_no = 0
    streets_untagged = 0
    lamps = 0
    crossings = 0
    police: SurroundingPlace | None = None
    emergency_phones = 0
    seen: set[tuple[str, int]] = set()

    for el in elements:
        key = (el.get("type", ""), int(el.get("id", 0)))
        if key in seen:
            continue
        seen.add(key)
        tags = el.get("tags") or {}

        if tags.get("highway") == "street_lamp":
            lamps += 1
            continue
        if tags.get("highway") == "crossing" or "crossing" in tags:
            crossings += 1
            continue
        if tags.get("emergency") == "phone":
            emergency_phones += 1
            continue
        if tags.get("amenity") == "police":
            coords = _element_coords(el)
            if coords is not None:
                distance = haversine_m(coords, campus)
                if distance <= radius and (police is None or distance < police.distance_m):
                    police = SurroundingPlace(
                        name=tags.get("name") or tags.get("name:ru") or "",
                        distance_m=round(distance),
                        walk_minutes=_walk_minutes(distance),
                        osm_url=f"https://www.openstreetmap.org/{el.get('type')}/{el.get('id')}",
                    )
            continue
        if "highway" in tags:
            lit = tags.get("lit")
            if lit in ("yes", "24/7", "automatic", "sunset-sunrise"):
                lit_yes += 1
            elif lit == "no":
                lit_no += 1
            else:
                streets_untagged += 1

    streets_total = lit_yes + lit_no + streets_untagged
    # Долю считаем от улиц, У КОТОРЫХ ТЕГ ЕСТЬ. Считать от всех — значит выдать
    # непроставленный тег за отсутствие фонарей, а это разные вещи.
    tagged = lit_yes + lit_no
    lit_share = round(100 * lit_yes / tagged) if tagged else None

    return DistrictInfo(
        radius_m=radius,
        streets_total=streets_total,
        streets_lit=lit_yes,
        streets_unlit=lit_no,
        streets_without_lit_tag=streets_untagged,
        lit_share_percent=lit_share,
        street_lamps=lamps,
        crossings=crossings,
        emergency_phones=emergency_phones,
        police=police,
        available=True,
    )


async def fetch_district(
    coords: Coordinates | None, radius: int = DEFAULT_RADIUS_M
) -> DistrictInfo | None:
    """Инфраструктура района вокруг кампуса. None — координат нет."""
    if coords is None:
        return None

    s = get_settings()
    cache = get_cache()
    key = f"osm-district:v1:{coords.lat:.4f},{coords.lon:.4f}:{radius}"

    async def produce() -> DistrictInfo:
        data = await _overpass(_build_district_query(coords, radius))
        return parse_district(data.get("elements") or [], coords, radius)

    try:
        return await cache.get_or_set(key, s.cache_ttl_resolve, produce)
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # noqa: BLE001
        log.warning("overpass district failed: %s", exc)
        return DistrictInfo(
            radius_m=radius,
            available=False,
            error="OpenStreetMap (Overpass) не ответил — данные о районе не собраны",
        )
