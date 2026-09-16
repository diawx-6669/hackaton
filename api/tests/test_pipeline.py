import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import RejectReason, Stage
from app.pipeline import stream_profile
from tests import fixtures
from tests.conftest import COMMONS_API, WIKIDATA_API, WIKIDATA_SPARQL, commons_handler


@pytest.fixture
def full_mock(api_mock):
    api_mock.get(WIKIDATA_API).mock(return_value=httpx.Response(200, json=fixtures.WBSEARCH))
    api_mock.get(WIKIDATA_SPARQL).mock(return_value=httpx.Response(200, json=fixtures.SPARQL))
    api_mock.get(COMMONS_API).mock(side_effect=commons_handler(fixtures.COMMONS_FIXTURES))
    return api_mock


async def collect_events(**kw):
    return [e async for e in stream_profile(**kw)]


async def test_stage_order_and_timer(full_mock):
    events = await collect_events(qid=fixtures.QID)
    stages = [e.stage for e in events]

    assert stages[0] is Stage.COLLECTING
    assert stages[-1] is Stage.DONE
    for expected in (Stage.RESOLVED, Stage.FOUND, Stage.DEDUPED, Stage.REJECTED, Stage.VERIFIED):
        assert expected in stages, f"нет этапа {expected}"
    # Таймер монотонно растёт
    assert all(a.elapsed_ms <= b.elapsed_ms for a, b in zip(events, events[1:]))


async def test_done_payload_is_a_profile(full_mock):
    events = await collect_events(qid=fixtures.QID)
    done = events[-1].payload
    assert done["university"]["id"] == fixtures.QID
    assert done["university"]["commons_category"] == "Kazakh-British Technical University"

    stats = done["stats"]
    assert stats["found"] > 0
    assert stats["duplicates"] >= 1, "файл из двух источников обязан схлопнуться"
    assert stats["verified"] + stats["needs_review"] + stats["rejected"] - stats["duplicates"] == stats["unique"]

    # Отклонённые фото всегда несут причину — это вкладка «Отклонено».
    for photo in done["rejected"]:
        assert photo["reject_reason"] and photo["reject_detail"]

    reasons = {p["reject_reason"] for p in done["rejected"]}
    assert RejectReason.NOT_A_PHOTO.value in reasons
    assert RejectReason.DUPLICATE.value in reasons

    # У каждой проверенной карточки есть кликабельный источник и улики.
    for photo in done["verified"]:
        assert photo["source_page_url"].startswith("https://")
        assert photo["evidence"]["signals"]


async def test_empty_categories_are_explained(full_mock):
    events = await collect_events(qid=fixtures.QID)
    buckets = events[-1].payload["by_category"]
    empty = [b for b in buckets if not b["photos"]]
    assert empty, "ожидали пустые категории до подключения классификатора"
    assert all(b["empty_reason"] for b in empty)


async def test_ambiguous_query_asks_for_choice(full_mock):
    events = await collect_events(q="KBTU")
    resolved = [e for e in events if e.stage is Stage.RESOLVED]
    assert resolved and resolved[-1].payload["needs_choice"] is True
    assert len(resolved[-1].payload["candidates"]) >= 2
    assert events[-1].stage is Stage.RESOLVED  # профиль не собираем, пока не выбрали


async def test_unknown_university_reports_error(api_mock):
    api_mock.get(WIKIDATA_API).mock(return_value=httpx.Response(200, json={"search": []}))
    api_mock.get(WIKIDATA_SPARQL).mock(
        return_value=httpx.Response(200, json={"results": {"bindings": []}})
    )
    events = await collect_events(q="этоневуз")
    assert events[-1].stage is Stage.ERROR


async def test_collector_failure_becomes_warning(api_mock):
    api_mock.get(WIKIDATA_API).mock(return_value=httpx.Response(200, json=fixtures.WBSEARCH))
    api_mock.get(WIKIDATA_SPARQL).mock(return_value=httpx.Response(200, json=fixtures.SPARQL))
    api_mock.get(COMMONS_API).mock(return_value=httpx.Response(503))
    events = await collect_events(qid=fixtures.QID)
    profile = events[-1].payload
    assert events[-1].stage is Stage.DONE
    assert profile["stats"]["found"] == 0
    assert any("не удалось" in w or "не ответил" in w for w in profile["warnings"])


def test_sse_endpoint_streams_events(full_mock):
    with TestClient(app) as client:
        with client.stream("GET", f"/api/profile?id={fixtures.QID}") as response:
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/event-stream")
            body = "".join(response.iter_text())
    assert "event: resolved" in body
    assert "event: deduped" in body
    assert "event: done" in body


def test_health_and_validation():
    with TestClient(app) as client:
        assert client.get("/api/health").json()["status"] == "ok"
        assert client.get("/api/profile").status_code == 422
