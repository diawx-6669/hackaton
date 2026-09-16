"""Шаг 1 ТЗ: поиск вуза в Wikidata (wbsearchentities + SPARQL)."""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Optional
from urllib.parse import urlparse

from app.config import get_settings
from app.models import Coordinates, University
from app.services.http import get_json
from app.services.textmatch import expand_query, similarity

log = logging.getLogger(__name__)


class UpstreamUnavailable(RuntimeError):
    """Wikidata не ответила ни на один запрос — это не «вуз не найден»."""


SEARCH_LANGUAGES = ("ru", "en", "kk")

# Point(76.9455 43.2352) -> (lon, lat)
_POINT_RE = re.compile(r"Point\(\s*(-?[\d.]+)\s+(-?[\d.]+)\s*\)")

_DETAILS_SPARQL = """
SELECT ?item ?itemLabel ?itemDescription ?coord ?cityCoord ?website ?commonsCat
       ?cityLabel ?countryLabel ?logo ?inception ?isEdu
WHERE {
  VALUES ?item { %(values)s }
  OPTIONAL { ?item wdt:P625 ?coord . }
  OPTIONAL { ?item wdt:P856 ?website . }
  OPTIONAL { ?item wdt:P373 ?commonsCat . }
  OPTIONAL { ?item wdt:P17 ?country . }
  OPTIONAL { ?item wdt:P154 ?logo . }
  OPTIONAL { ?item wdt:P571 ?inception . }
  OPTIONAL {
    ?item wdt:P131 ?city .
    OPTIONAL { ?city wdt:P625 ?cityCoord . }
  }
  BIND((EXISTS { ?item wdt:P31/wdt:P279* wd:Q2385804 }
     || EXISTS { ?item wdt:P31/wdt:P279* wd:Q4671277 }
     || EXISTS { ?item wdt:P31/wdt:P279* wd:Q38723 }) AS ?isEdu)
  SERVICE wikibase:label { bd:serviceParam wikibase:language "ru,en,kk". }
}
"""


def _parse_point(value: str | None) -> Optional[Coordinates]:
    if not value:
        return None
    m = _POINT_RE.search(value)
    if not m:
        return None
    lon, lat = float(m.group(1)), float(m.group(2))
    return Coordinates(lat=lat, lon=lon)


def parse_point(value: str | None) -> Optional[Coordinates]:
    """Публичная обёртка над разбором WKT-точки Wikidata."""
    return _parse_point(value)


async def _search_once(query: str, language: str, limit: int) -> list[dict[str, Any]] | None:
    """Возвращает список совпадений, либо None если запрос вообще не прошёл."""
    s = get_settings()
    try:
        data = await get_json(
            s.wikidata_api,
            {
                "action": "wbsearchentities",
                "search": query,
                "language": language,
                "uselang": language,
                "type": "item",
                "limit": limit,
                "format": "json",
                "formatversion": 2,
            },
        )
    except Exception as exc:  # один упавший язык не должен ронять поиск
        log.warning("wbsearchentities(%s, %s) failed: %s", query, language, exc)
        return None
    return data.get("search", []) or []


async def search_entities(query: str, limit: int = 12) -> dict[str, dict[str, Any]]:
    """Ищем по всем вариантам запроса и языкам параллельно, склеиваем по QID."""
    variants = expand_query(query)
    tasks = [
        _search_once(variant, lang, limit)
        for variant in variants
        for lang in SEARCH_LANGUAGES
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    merged: dict[str, dict[str, Any]] = {}
    ok = 0
    for res in results:
        if isinstance(res, BaseException) or res is None:
            continue
        ok += 1
        for hit in res:
            qid = hit.get("id")
            if not qid:
                continue
            prev = merged.get(qid)
            if prev is None:
                merged[qid] = {
                    "id": qid,
                    "label": hit.get("label") or hit.get("match", {}).get("text") or qid,
                    "description": hit.get("description"),
                    "aliases": [],
                }
                prev = merged[qid]
            matched = (hit.get("match") or {}).get("text")
            if matched and matched not in prev["aliases"] and matched != prev["label"]:
                prev["aliases"].append(matched)
            if not prev.get("description") and hit.get("description"):
                prev["description"] = hit["description"]

    if ok == 0 and tasks:
        raise UpstreamUnavailable(
            "Wikidata не ответила ни на один поисковый запрос — проверьте сеть/прокси"
        )
    return merged


async def fetch_details(qids: list[str]) -> dict[str, dict[str, Any]]:
    """Добираем координаты/сайт/город/категорию Commons одним SPARQL-запросом."""
    if not qids:
        return {}
    s = get_settings()
    values = " ".join(f"wd:{q}" for q in qids)
    query = _DETAILS_SPARQL % {"values": values}
    try:
        data = await get_json(
            s.wikidata_sparql,
            {"query": query, "format": "json"},
            headers={"Accept": "application/sparql-results+json"},
        )
    except Exception as exc:
        log.warning("SPARQL details failed: %s", exc)
        return {}

    out: dict[str, dict[str, Any]] = {}
    for row in data.get("results", {}).get("bindings", []):
        uri = row.get("item", {}).get("value", "")
        qid = uri.rsplit("/", 1)[-1]
        if not qid:
            continue
        rec = out.setdefault(qid, {})

        def take(key: str, dest: str) -> None:
            val = row.get(key, {}).get("value")
            if val and not rec.get(dest):
                rec[dest] = val

        take("itemLabel", "label")
        take("itemDescription", "description")
        take("coord", "coord")
        take("cityCoord", "city_coord")
        take("website", "website")
        take("commonsCat", "commons_category")
        take("cityLabel", "city")
        take("countryLabel", "country")
        take("logo", "logo")
        take("inception", "inception")
        is_edu = row.get("isEdu", {}).get("value")
        if is_edu is not None:
            rec["is_edu"] = is_edu in ("true", "1")
    return out


def _looks_like_institution(name: str, description: str | None) -> bool:
    """Подстраховка, если SPARQL не ответил: смотрим на текст описания."""
    blob = f"{name} {description or ''}".lower()
    keywords = (
        "univers", "college", "institut", "academy", "school",
        "универ", "институт", "академ", "колледж", "вуз", "политех",
        "university", "универcитет", "жоғары оқу",
    )
    return any(k in blob for k in keywords)


async def resolve(query: str, limit: int = 8) -> list[University]:
    """Возвращает отсортированный список кандидатов-вузов."""
    hits = await search_entities(query)
    if not hits:
        return []

    # Предварительно ранжируем по нечёткому совпадению и берём топ для SPARQL.
    prescored: list[tuple[float, dict[str, Any]]] = []
    for hit in hits.values():
        score = similarity(query, hit["label"], hit.get("description"), *hit["aliases"])
        prescored.append((score, hit))
    prescored.sort(key=lambda p: p[0], reverse=True)
    shortlist = [h for _, h in prescored[: max(limit * 3, 20)]]

    details = await fetch_details([h["id"] for h in shortlist])

    universities: list[University] = []
    for hit in shortlist:
        qid = hit["id"]
        det = details.get(qid, {})
        name = det.get("label") or hit["label"]
        description = hit.get("description") or det.get("description")

        is_edu = det.get("is_edu")
        if is_edu is False:
            continue
        if is_edu is None and not _looks_like_institution(name, description):
            # SPARQL не подтвердил тип и текст не похож на вуз — пропускаем.
            continue

        coords = _parse_point(det.get("coord")) or _parse_point(det.get("city_coord"))
        website = det.get("website")
        if website and not urlparse(website).scheme:
            website = f"https://{website}"

        universities.append(
            University(
                id=qid,
                name=name,
                description=description,
                aliases=hit.get("aliases", []),
                city=det.get("city"),
                country=det.get("country"),
                coordinates=coords,
                website=website,
                commons_category=det.get("commons_category"),
                logo_url=det.get("logo"),
                inception=(det.get("inception") or "")[:10] or None,
                wikidata_url=f"https://www.wikidata.org/wiki/{qid}",
                match_score=similarity(query, name, *hit.get("aliases", [])),
            )
        )

    # Финальная сортировка: похожесть важнее, но полнота данных решает ничьи.
    def rank(u: University) -> tuple[float, int, int]:
        completeness = int(u.coordinates is not None) + int(bool(u.commons_category))
        return (u.match_score, completeness, int(bool(u.website)))

    universities.sort(key=rank, reverse=True)
    return universities[:limit]


def is_ambiguous(candidates: list[University]) -> bool:
    """Неоднозначно, если лидер не оторвался от второго места."""
    if len(candidates) < 2:
        return False
    top, second = candidates[0], candidates[1]
    if top.match_score < 0.9:
        return True
    return (top.match_score - second.match_score) < 0.08
