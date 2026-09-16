"""Шаг 1 ТЗ: поиск вуза в Wikidata (wbsearchentities + SPARQL)."""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Optional
from urllib.parse import urlparse

from app.config import get_settings
from app.models import Coordinates, University
from app.services.cache import get_cache
from app.services.http import get_json
from app.services.textmatch import expand_query, similarity

log = logging.getLogger(__name__)


class UpstreamUnavailable(RuntimeError):
    """Wikidata не ответила ни на один запрос — это не «вуз не найден»."""


SEARCH_LANGUAGES = ("ru", "en", "kk")

# Point(76.9455 43.2352) -> (lon, lat)
_POINT_RE = re.compile(r"Point\(\s*(-?[\d.]+)\s+(-?[\d.]+)\s*\)")

_DETAILS_SPARQL = """
SELECT ?item ?itemLabel ?itemDescription ?enLabel ?alias ?coord ?cityCoord ?website
       ?commonsCat ?cityLabel ?countryLabel ?logo ?inception ?isEdu
WHERE {
  VALUES ?item { %(values)s }
  # Английское название и алиасы нужны не для показа, а как улика: файлы на
  # Commons почти всегда подписаны по-английски или аббревиатурой (KBTU).
  OPTIONAL { ?item rdfs:label ?enLabel . FILTER(lang(?enLabel) = "en") }
  OPTIONAL { ?item skos:altLabel ?alias . FILTER(lang(?alias) IN ("ru", "en", "kk")) }
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
        take("enLabel", "en_label")

        alias = row.get("alias", {}).get("value")
        if alias:
            aliases = rec.setdefault("aliases", [])
            if alias not in aliases:
                aliases.append(alias)
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


def _merge_aliases(name: str, search_aliases: list[str], details: dict[str, Any]) -> list[str]:
    """Все известные имена вуза: из поиска, английская метка и altLabel из Wikidata.

    Именно по ним потом ищется упоминание вуза в метаданных файла, поэтому
    английское название и аббревиатуры здесь важнее, чем для показа.
    """
    merged: list[str] = []
    for candidate in [*search_aliases, details.get("en_label"), *details.get("aliases", [])]:
        if not candidate:
            continue
        text = candidate.strip()
        if text and text != name and text not in merged:
            merged.append(text)
    return merged[:12]


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
    """Возвращает отсортированный список кандидатов-вузов (с кешем)."""
    s = get_settings()
    if not s.cache_enabled:
        return await _resolve_uncached(query, limit)

    cache = get_cache()
    key = cache.key("resolve", query.strip().lower(), limit)
    raw = await cache.get_or_set(
        key,
        s.cache_ttl_resolve,
        lambda: _resolve_and_dump(query, limit),
    )
    return [University.model_validate(item) for item in raw]


async def _resolve_and_dump(query: str, limit: int) -> list[dict[str, Any]]:
    results = await _resolve_uncached(query, limit)
    return [u.model_dump(mode="json") for u in results]


async def _resolve_uncached(query: str, limit: int = 8) -> list[University]:
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
        aliases = _merge_aliases(name, hit.get("aliases", []), det)

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
                aliases=aliases,
                city=det.get("city"),
                country=det.get("country"),
                coordinates=coords,
                website=website,
                commons_category=det.get("commons_category"),
                logo_url=det.get("logo"),
                inception=(det.get("inception") or "")[:10] or None,
                wikidata_url=f"https://www.wikidata.org/wiki/{qid}",
                match_score=similarity(query, name, *aliases),
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
