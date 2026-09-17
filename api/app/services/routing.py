"""Сколько добираться: маршруты OSRM и честная оценка по прямой (п.8 ТЗ).

Важное ограничение, из-за которого этот модуль выглядит именно так: публичный
демо-сервер OSRM отдаёт только автомобильный профиль. Пешеходного там нет.
Поэтому «пешком 8 минут» мы не пишем как факт — для пешего участка честно
указываем расстояние по прямой и помечаем это словом «оценка». Как только
появится свой OSRM с профилем foot, достаточно поменять profile в запросе.
"""
from __future__ import annotations

import asyncio
import logging

from app.config import get_settings
from app.models import Coordinates, Logistics, RouteLeg
from app.services.cache import get_cache
from app.services.evidence import haversine_m
from app.services.http import get_json

log = logging.getLogger(__name__)

WALK_SPEED_M_PER_MIN = 75.0  # 4.5 км/ч


def straight_leg(
    key: str, title: str, from_name: str, to_name: str, a: Coordinates, b: Coordinates
) -> RouteLeg:
    distance = haversine_m(a, b)
    return RouteLeg(
        key=key,
        title=title,
        from_name=from_name,
        to_name=to_name,
        distance_m=round(distance),
        minutes=max(1, round(distance / WALK_SPEED_M_PER_MIN)),
        mode="straight",
        note="по прямой, пешком 4,5 км/ч — реальный путь длиннее",
    )


async def _osrm_route(a: Coordinates, b: Coordinates) -> tuple[float, float] | None:
    """(метры, секунды) по автомобильному маршруту или None, если OSRM не ответил."""
    s = get_settings()
    url = f"{s.osrm_endpoint}/route/v1/driving/{a.lon},{a.lat};{b.lon},{b.lat}"
    data = await get_json(url, {"overview": "false"}, retries=0)
    routes = data.get("routes") or []
    if not routes:
        return None
    route = routes[0]
    return float(route["distance"]), float(route["duration"])


async def driving_leg(
    key: str, title: str, from_name: str, to_name: str, a: Coordinates, b: Coordinates
) -> RouteLeg:
    """Маршрут OSRM; если сервис молчит — та же пара точек, но по прямой."""
    try:
        result = await _osrm_route(a, b)
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # noqa: BLE001
        log.warning("OSRM %s failed: %s", key, exc)
        result = None

    if result is None:
        leg = straight_leg(key, title, from_name, to_name, a, b)
        leg.note = "OSRM не ответил — показано расстояние по прямой"
        return leg

    distance, seconds = result
    return RouteLeg(
        key=key,
        title=title,
        from_name=from_name,
        to_name=to_name,
        distance_m=round(distance),
        minutes=max(1, round(seconds / 60)),
        mode="driving",
        note="маршрут OSRM, автомобиль, без учёта пробок",
    )


async def build_logistics(
    campus: Coordinates | None,
    campus_name: str,
    city_center: Coordinates | None,
    city_name: str | None,
    dorm: tuple[str, Coordinates] | None,
) -> Logistics | None:
    """Участки пути, которые можно посчитать по имеющимся координатам."""
    if campus is None:
        return None

    jobs: list = []
    if dorm is not None:
        dorm_name, dorm_coords = dorm
        # Пеший участок: только по прямой и только с пометкой.
        jobs.append(
            straight_leg(
                "dorm_walk",
                "От общежития до кампуса пешком",
                dorm_name or "общежитие",
                campus_name,
                dorm_coords,
                campus,
            )
        )
        jobs.append(
            driving_leg(
                "dorm_drive",
                "От общежития до кампуса на машине",
                dorm_name or "общежитие",
                campus_name,
                dorm_coords,
                campus,
            )
        )
    if city_center is not None and haversine_m(city_center, campus) > 200:
        jobs.append(
            driving_leg(
                "city_drive",
                "От центра города до кампуса",
                city_name or "центр города",
                campus_name,
                city_center,
                campus,
            )
        )

    if not jobs:
        return Logistics(
            legs=[],
            available=True,
            error="Не с чем считать: в Wikidata нет координат города, в OSM рядом нет общежитий",
        )

    legs: list[RouteLeg] = []
    for job in jobs:
        legs.append(job if isinstance(job, RouteLeg) else await job)
    return Logistics(legs=legs, available=True)
