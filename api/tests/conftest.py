"""Фикстуры: все внешние API замоканы, тесты не ходят в сеть."""
from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
import respx

from app.services.cache import TTLCache, set_cache
from app.services.http import close_client

WIKIDATA_API = "https://www.wikidata.org/w/api.php"
WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"


@pytest.fixture(autouse=True)
async def _reset_state():
    """Каждый тест стартует с чистым HTTP-клиентом и пустым кешем в памяти."""
    set_cache(TTLCache(directory=None))
    await close_client()
    yield
    set_cache(TTLCache(directory=None))
    await close_client()


def sparql_binding(**kwargs: Any) -> dict[str, Any]:
    return {k: {"value": v} for k, v in kwargs.items() if v is not None}


@pytest.fixture
def api_mock():
    """respx-роутер с хендлерами по action/list — как настоящие MediaWiki API."""
    with respx.mock(assert_all_called=False) as router:
        yield router


def commons_handler(fixtures: dict[str, Any]):
    """Отдаёт нужный кусок фикстуры в зависимости от list=/prop= в запросе."""

    def handler(request: httpx.Request) -> httpx.Response:
        params = dict(request.url.params)
        if params.get("list") == "categorymembers":
            members = fixtures["categories"].get(params["cmtitle"], [])
            return httpx.Response(200, json={"query": {"categorymembers": members}})
        if params.get("list") == "search":
            hits = fixtures.get("search", {}).get(params["srsearch"], [])
            return httpx.Response(200, json={"query": {"search": hits}})
        if params.get("list") == "geosearch":
            return httpx.Response(200, json={"query": {"geosearch": fixtures.get("geosearch", [])}})
        if "imageinfo" in (params.get("prop") or ""):
            titles = params["titles"].split("|")
            pages = [fixtures["pages"][t] for t in titles if t in fixtures["pages"]]
            return httpx.Response(200, json={"query": {"pages": pages}})
        return httpx.Response(200, json={"query": {}})

    return handler


def dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False)
