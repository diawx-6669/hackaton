import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests import fixtures
from tests.conftest import COMMONS_API, WIKIDATA_API, WIKIDATA_SPARQL, commons_handler


@pytest.fixture
def full_mock(api_mock):
    api_mock.get(WIKIDATA_API).mock(return_value=httpx.Response(200, json=fixtures.WBSEARCH))
    api_mock.get(WIKIDATA_SPARQL).mock(return_value=httpx.Response(200, json=fixtures.SPARQL))
    api_mock.get(COMMONS_API).mock(side_effect=commons_handler(fixtures.COMMONS_FIXTURES))
    return api_mock


def test_compare_two_universities(full_mock):
    with TestClient(app) as client:
        r = client.get("/api/compare", params={"a_id": fixtures.QID, "b_id": fixtures.QID})
    assert r.status_code == 200
    body = r.json()

    assert body["a"]["university"]["id"] == fixtures.QID
    assert body["b"]["university"]["id"] == fixtures.QID
    keys = {row["key"] for row in body["rows"]}
    assert {"city", "verified", "confidence", "categories", "took"} <= keys
    # Одинаковые вузы — ничья по всем содержательным строкам.
    # Время сборки исключено осознанно: второй прогон берёт данные из кеша
    # и честно оказывается быстрее.
    for row in body["rows"]:
        if row["winner"] is not None and row["key"] != "took":
            assert row["winner"] == "tie", row

    assert body["took_ms"] >= 0


def test_compare_requires_both_sides():
    with TestClient(app) as client:
        assert client.get("/api/compare", params={"a": "КБТУ"}).status_code == 422


def test_compare_reports_which_side_failed(api_mock):
    api_mock.get(WIKIDATA_API).mock(return_value=httpx.Response(200, json={"search": []}))
    api_mock.get(WIKIDATA_SPARQL).mock(
        return_value=httpx.Response(200, json={"results": {"bindings": []}})
    )
    with TestClient(app) as client:
        r = client.get("/api/compare", params={"a": "нетвуза", "b": "тожеНет"})
    assert r.status_code == 404
    assert r.json()["detail"].startswith("[a]") or r.json()["detail"].startswith("[b]")


def test_qid_alias_from_spec_works(full_mock):
    with TestClient(app) as client:
        r = client.get("/api/profile.json", params={"qid": fixtures.QID})
    assert r.status_code == 200
    assert r.json()["university"]["id"] == fixtures.QID
