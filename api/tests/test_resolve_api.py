import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests import fixtures
from tests.conftest import WIKIDATA_API, WIKIDATA_SPARQL


@pytest.fixture
def wikidata_mock(api_mock):
    api_mock.get(WIKIDATA_API).mock(return_value=httpx.Response(200, json=fixtures.WBSEARCH))
    api_mock.get(WIKIDATA_SPARQL).mock(return_value=httpx.Response(200, json=fixtures.SPARQL))
    return api_mock


def test_resolve_endpoint(wikidata_mock):
    with TestClient(app) as client:
        r = client.get("/api/resolve", params={"q": "КБТУ"})
    assert r.status_code == 200
    body = r.json()
    assert body["query"] == "КБТУ"
    assert isinstance(body["ambiguous"], bool)
    assert body["took_ms"] >= 0
    top = body["candidates"][0]
    assert top["id"] == fixtures.QID
    assert top["city"] == "Алматы"
    assert top["coordinates"]["lat"] == 43.236


def test_resolve_requires_min_length():
    with TestClient(app) as client:
        assert client.get("/api/resolve", params={"q": "a"}).status_code == 422


def test_resolve_reports_upstream_failure(api_mock):
    api_mock.get(WIKIDATA_API).mock(side_effect=httpx.ConnectError("no network"))
    api_mock.get(WIKIDATA_SPARQL).mock(side_effect=httpx.ConnectError("no network"))
    with TestClient(app) as client:
        r = client.get("/api/resolve", params={"q": "КБТУ"})
    # Все языковые запросы упали → честный пустой результат, а не выдуманный вуз.
    assert r.status_code == 200
    assert r.json()["candidates"] == []
