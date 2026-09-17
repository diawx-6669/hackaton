"""Шаг 1 ТЗ: поиск вуза в Wikidata (wbsearchentities + SPARQL)."""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Optional
from urllib.parse import quote, urlparse

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


# Классы, по которым Action API может понять, что это вуз. SPARQL проверяет
# P31/P279* транзитивно, Action API так не умеет — поэтому здесь плоский
# список самых частых значений P31. Не нашли совпадения — НЕ пишем is_edu=False,
# а оставляем None: пусть решает текстовая подстраховка, а не догадка.
_EDU_CLASSES = {
    "Q3918",  # университет
    "Q875538",  # публичный университет
    "Q902104",  # частный университет
    "Q3354859",  # коллегиальный университет
    "Q1371037",  # технический университет
    "Q189004",  # колледж
    "Q1664720",  # институт
    "Q2385804",  # образовательное учреждение
    "Q4671277",  # академическое учреждение
    "Q38723",  # высшее учебное заведение
    "Q62078547",  # общественный исследовательский университет
    "Q15936437",  # исследовательский университет
    "Q23002054",  # частное некоммерческое учебное заведение
}

# Свойства, которые вытаскиваем из claims Action API.
_CLAIM_MAP = {
    "P625": "coord",
    "P856": "website",
    "P373": "commons_category",
    "P154": "logo",
    "P571": "inception",
}


def _claim_values(entity: dict[str, Any], prop: str) -> list[Any]:
    out = []
    for claim in entity.get("claims", {}).get(prop, []):
        snak = claim.get("mainsnak", {})
        if snak.get("snaktype") != "value":
            continue
        value = snak.get("datavalue", {}).get("value")
        if value is not None:
            out.append(value)
    return out


def _entity_label(entity: dict[str, Any], key: str = "labels") -> dict[str, str]:
    return {lang: v.get("value", "") for lang, v in (entity.get(key) or {}).items()}


async def _wbgetentities(qids: list[str], props: str) -> dict[str, dict[str, Any]]:
    s = get_settings()
    out: dict[str, dict[str, Any]] = {}
    # Action API принимает не больше 50 идентификаторов за запрос.
    for i in range(0, len(qids), 50):
        chunk = qids[i : i + 50]
        data = await get_json(
            s.wikidata_api,
            {
                "action": "wbgetentities",
                "ids": "|".join(chunk),
                "props": props,
                "languages": "ru|en|kk",
                "format": "json",
                "origin": "*",
            },
        )
        out.update(data.get("entities") or {})
    return out


async def _fetch_details_action(qids: list[str]) -> dict[str, dict[str, Any]]:
    """Запасной путь, когда SPARQL недоступен (403, лимиты, таймаут).

    Action API отдаёт те же P625/P856/P373/P17/P131/P154/P571, только без
    транзитивной проверки типа и с QID вместо названий города и страны —
    за ними идём вторым запросом. Данных чуть меньше, но профиль собирается:
    падение одного источника не должно ронять весь ответ (п.2 ТЗ).
    """
    entities = await _wbgetentities(qids, "labels|descriptions|aliases|claims")

    out: dict[str, dict[str, Any]] = {}
    linked: set[str] = set()  # QID города и страны — за их названиями сходим отдельно
    for qid, entity in entities.items():
        if entity.get("missing") is not None:
            continue
        rec: dict[str, Any] = {}
        labels = _entity_label(entity)
        descriptions = _entity_label(entity, "descriptions")
        label = labels.get("ru") or labels.get("en") or labels.get("kk")
        if label:
            rec["label"] = label
        if labels.get("en"):
            rec["en_label"] = labels["en"]
        description = descriptions.get("ru") or descriptions.get("en")
        if description:
            rec["description"] = description

        aliases: list[str] = []
        for lang_aliases in (entity.get("aliases") or {}).values():
            for a in lang_aliases:
                value = a.get("value")
                if value and value not in aliases:
                    aliases.append(value)
        if aliases:
            rec["aliases"] = aliases

        for prop, key in _CLAIM_MAP.items():
            values = _claim_values(entity, prop)
            if not values:
                continue
            value = values[0]
            if key == "coord" and isinstance(value, dict):
                # Приводим к тому же виду, что отдаёт SPARQL: Point(lon lat).
                rec["coord"] = f"Point({value['longitude']} {value['latitude']})"
            elif key == "inception" and isinstance(value, dict):
                rec["inception"] = str(value.get("time", "")).lstrip("+")
            elif key == "logo" and isinstance(value, str):
                rec["logo"] = (
                    "https://commons.wikimedia.org/wiki/Special:FilePath/"
                    + quote(value.replace(" ", "_"))
                )
            elif isinstance(value, str):
                rec[key] = value

        for prop, key in (("P131", "city"), ("P17", "country")):
            values = _claim_values(entity, prop)
            if values and isinstance(values[0], dict) and values[0].get("id"):
                rec[f"{key}_qid"] = values[0]["id"]
                linked.add(values[0]["id"])

        types = {
            v["id"]
            for v in _claim_values(entity, "P31")
            if isinstance(v, dict) and v.get("id")
        }
        if types & _EDU_CLASSES:
            rec["is_edu"] = True

        out[qid] = rec

    # Названия города и страны + координаты города (если у вуза нет своих).
    if linked:
        try:
            places = await _wbgetentities(sorted(linked), "labels|claims")
        except Exception as exc:  # noqa: BLE001 — без названий профиль всё равно жив
            log.warning("wbgetentities places failed: %s", exc)
            places = {}
        for rec in out.values():
            for key in ("city", "country"):
                place = places.get(rec.pop(f"{key}_qid", "") or "")
                if not place or place.get("missing") is not None:
                    continue
                labels = _entity_label(place)
                name = labels.get("ru") or labels.get("en") or labels.get("kk")
                if name:
                    rec[key] = name
                if key == "city" and not rec.get("city_coord"):
                    coords = _claim_values(place, "P625")
                    if coords and isinstance(coords[0], dict):
                        rec["city_coord"] = (
                            f"Point({coords[0]['longitude']} {coords[0]['latitude']})"
                        )
    return out


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
        log.warning("SPARQL details failed: %s — пробуем Action API", exc)
        try:
            return await _fetch_details_action(qids)
        except Exception as fallback_exc:  # noqa: BLE001
            log.warning("wbgetentities fallback failed: %s", fallback_exc)
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
    rejected_by_type: list[University] = []
    for hit in shortlist:
        qid = hit["id"]
        det = details.get(qid, {})
        name = det.get("label") or hit["label"]
        description = hit.get("description") or det.get("description")
        aliases = _merge_aliases(name, hit.get("aliases", []), det)

        is_edu = det.get("is_edu")
        looks_like = _looks_like_institution(name, description)

        coords = _parse_point(det.get("coord")) or _parse_point(det.get("city_coord"))
        website = det.get("website")
        if website and not urlparse(website).scheme:
            website = f"https://{website}"

        candidate = University(
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

        if is_edu is False:
            # Wikidata уверенно говорит, что это не учебное заведение.
            continue
        if is_edu is None and not looks_like:
            # Тип не подтверждён и текст не похож на вуз — в запас, на случай,
            # если строгий фильтр не оставит вообще ничего.
            rejected_by_type.append(candidate)
            continue
        universities.append(candidate)

    # Финальная сортировка: похожесть важнее, но полнота данных решает ничьи.
    def rank(u: University) -> tuple[float, int, int]:
        completeness = int(u.coordinates is not None) + int(bool(u.commons_category))
        return (u.match_score, completeness, int(bool(u.website)))

    # Лучше показать сомнительных кандидатов, чем сказать «ничего не найдено»:
    # у малоизвестных вузов тип в Wikidata часто просто не проставлен.
    if not universities and rejected_by_type:
        universities = rejected_by_type

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
