import httpx
import pytest

from app.services import wikidata
from tests import fixtures
from tests.conftest import WIKIDATA_API, WIKIDATA_SPARQL


@pytest.fixture
def wikidata_mock(api_mock):
    api_mock.get(WIKIDATA_API).mock(return_value=httpx.Response(200, json=fixtures.WBSEARCH))
    api_mock.get(WIKIDATA_SPARQL).mock(return_value=httpx.Response(200, json=fixtures.SPARQL))
    return api_mock


async def test_resolve_returns_university_with_metadata(wikidata_mock):
    results = await wikidata.resolve("КБТУ")
    assert results, "ожидали хотя бы одного кандидата"
    top = results[0]
    assert top.id == fixtures.QID
    assert top.city == "Алматы"
    assert top.website == "https://kbtu.edu.kz/"
    assert top.commons_category == "Kazakh-British Technical University"
    assert top.coordinates is not None
    assert round(top.coordinates.lat, 3) == 43.236
    assert round(top.coordinates.lon, 3) == 76.929
    assert top.wikidata_url.endswith(fixtures.QID)


async def test_resolve_marks_ambiguity(wikidata_mock):
    results = await wikidata.resolve("KBTU")
    assert len(results) >= 2
    assert wikidata.is_ambiguous(results) is True


async def test_resolve_empty_on_no_hits(api_mock):
    api_mock.get(WIKIDATA_API).mock(return_value=httpx.Response(200, json={"search": []}))
    api_mock.get(WIKIDATA_SPARQL).mock(return_value=httpx.Response(200, json={"results": {"bindings": []}}))
    assert await wikidata.resolve("нетакоговуза") == []


async def test_resolve_survives_sparql_failure(api_mock):
    api_mock.get(WIKIDATA_API).mock(return_value=httpx.Response(200, json=fixtures.WBSEARCH))
    api_mock.get(WIKIDATA_SPARQL).mock(return_value=httpx.Response(500))
    results = await wikidata.resolve("КБТУ")
    # Без SPARQL остаётся текстовая эвристика: вуз всё равно найден, но без координат.
    assert results and results[0].coordinates is None


def test_parse_point():
    c = wikidata.parse_point("Point(76.929 43.236)")
    assert c is not None and (c.lat, c.lon) == (43.236, 76.929)
    assert wikidata.parse_point(None) is None
