import asyncio

import httpx
import pytest

from app.services import wikidata
from app.services.cache import TTLCache, set_cache
from tests import fixtures
from tests.conftest import WIKIDATA_API, WIKIDATA_SPARQL


def test_ttl_expiry(monkeypatch):
    cache = TTLCache(directory=None)
    now = [1000.0]
    monkeypatch.setattr("app.services.cache.time.time", lambda: now[0])

    cache.set("k", {"a": 1}, ttl=10)
    assert cache.get("k") == {"a": 1}
    now[0] += 11
    assert cache.get("k") is None


def test_file_layer_survives_process_restart(tmp_path):
    first = TTLCache(directory=tmp_path)
    first.set(TTLCache.key("ns", "x"), [1, 2, 3], ttl=60)

    # Новый объект = новый процесс: память пуста, значение приходит из файла.
    second = TTLCache(directory=tmp_path)
    assert second.get(TTLCache.key("ns", "x")) == [1, 2, 3]
    assert second.hits == 1


def test_key_includes_schema_version():
    assert TTLCache.key("ns", "a").startswith("v1:ns:")
    assert TTLCache.key("ns", "a") != TTLCache.key("ns", "b")


async def test_concurrent_callers_produce_once():
    cache = TTLCache(directory=None)
    calls = 0

    async def producer():
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.02)
        return {"value": calls}

    results = await asyncio.gather(*(cache.get_or_set("k", 60, producer) for _ in range(5)))
    assert calls == 1
    assert all(r == {"value": 1} for r in results)


async def test_empty_result_is_not_cached():
    cache = TTLCache(directory=None)
    calls = 0

    async def producer():
        nonlocal calls
        calls += 1
        return [] if calls == 1 else ["data"]

    assert await cache.get_or_set("k", 60, producer) == []
    # Разовый сбой не должен на сутки залипнуть как «ничего не найдено».
    assert await cache.get_or_set("k", 60, producer) == ["data"]


async def test_resolve_second_call_hits_cache(api_mock):
    cache = TTLCache(directory=None)
    set_cache(cache)
    route = api_mock.get(WIKIDATA_API).mock(
        return_value=httpx.Response(200, json=fixtures.WBSEARCH)
    )
    api_mock.get(WIKIDATA_SPARQL).mock(return_value=httpx.Response(200, json=fixtures.SPARQL))

    first = await wikidata.resolve("КБТУ")
    calls_after_first = route.call_count
    second = await wikidata.resolve("КБТУ")

    assert route.call_count == calls_after_first, "второй запрос не должен ходить в сеть"
    assert [u.id for u in first] == [u.id for u in second]
    assert cache.stats()["hits"] >= 1
