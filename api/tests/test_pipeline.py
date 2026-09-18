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


async def test_wikidata_down_is_reported_as_source_failure(api_mock):
    import httpx as _httpx

    api_mock.get(WIKIDATA_API).mock(side_effect=_httpx.ConnectError("no network"))
    api_mock.get(WIKIDATA_SPARQL).mock(side_effect=_httpx.ConnectError("no network"))
    events = await collect_events(q="КБТУ")
    last = events[-1]
    assert last.stage is Stage.ERROR
    # Недоступный источник не должен выглядеть как «такого вуза нет».
    assert "не найден" not in last.message
    assert "Wikidata" in last.message


async def test_photos_land_in_their_categories(full_mock):
    events = await collect_events(qid=fixtures.QID)
    profile = events[-1].payload

    by_cat = {b["category"]: b for b in profile["by_category"]}
    dorm_titles = [p["title"] for p in by_cat["dorms"]["photos"]]
    library_titles = [p["title"] for p in by_cat["libraries"]["photos"]]
    assert any("dormitory" in t for t in dorm_titles)
    assert any("library" in t for t in library_titles)

    # Категория подписана источником — не выдаём эвристику за CLIP.
    for bucket in profile["by_category"]:
        for photo in bucket["photos"]:
            assert photo["category_source"] == "metadata"

    # Пустая категория честно объясняет, что подтверждённых фото нет.
    empty = [b for b in profile["by_category"] if not b["photos"]]
    assert all("не найдено" in b["empty_reason"] for b in empty)


async def test_logo_is_rejected_as_junk_not_just_as_svg(full_mock):
    events = await collect_events(qid=fixtures.QID)
    rejected = {p["title"]: p for p in events[-1].payload["rejected"]}
    logo = rejected["KBTU logo.svg"]
    assert logo["reject_reason"] and logo["reject_detail"]


async def test_classified_stage_is_streamed(full_mock):
    events = await collect_events(qid=fixtures.QID)
    classified = [e for e in events if e.stage is Stage.CLASSIFIED]
    assert classified and classified[0].counts["classified"] >= 2


async def test_qid_entry_still_knows_university_aliases(full_mock):
    """Вход по постоянной ссылке /u/QID не должен терять алиасы вуза."""
    events = await collect_events(qid=fixtures.QID)
    uni = events[-1].payload["university"]
    assert "KBTU" in uni["aliases"]

    # Файлы на Commons подписаны по-английски — улика обязана срабатывать.
    verified = events[-1].payload["verified"]
    assert verified
    assert any(p["evidence"]["name_mentions"] for p in verified)


async def test_duplicates_carry_evidence_too(full_mock):
    events = await collect_events(qid=fixtures.QID)
    dups = [p for p in events[-1].payload["rejected"] if p["reject_reason"] == "duplicate"]
    assert dups, "в фикстурах есть файл из двух источников"
    for photo in dups:
        assert photo["evidence"]["signals"], "у дубликата тоже должен быть разбор улик"
        assert photo["reject_reason"] == "duplicate", "причина отказа не должна перезаписаться"


def test_deployment_warnings_fire_on_default_config(caplog):
    """Незаданные User-Agent и CORS молча ломают прод — они обязаны кричать в логе."""
    import logging

    from app.config import Settings
    from app.main import _check_deployment_config

    # _env_file=None — иначе результат теста зависел бы от локального .env
    # разработчика, и на чужой машине он падал бы без причины.
    with caplog.at_level(logging.WARNING, logger="campuslens"):
        _check_deployment_config(Settings(_env_file=None))
    text = " ".join(r.message for r in caplog.records)
    assert "CAMPUSLENS_USER_AGENT" in text
    assert "CORS" in text
    assert "CAMPUSLENS_AUTH_SECRET" in text

    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="campuslens"):
        _check_deployment_config(
            Settings(
                _env_file=None,
                user_agent="CampusLens/1.0 (mailto:me@example.com)",
                cors_origins="https://campuslens.vercel.app",
                auth_secret="long-random-secret",
            )
        )
    assert not caplog.records, "правильная конфигурация не должна ничего предупреждать"


async def test_obscure_university_without_category_or_coords_still_gets_photos(api_mock):
    """Главный кейс покрытия: у малоизвестного вуза нет ни P373, ни P625."""
    import httpx as _httpx

    api_mock.get(WIKIDATA_API).mock(
        return_value=_httpx.Response(
            200,
            json={
                "search": [
                    {
                        "id": fixtures.OBSCURE_QID,
                        "label": fixtures.OBSCURE_NAME,
                        "description": "university in Kazakhstan",
                    }
                ]
            },
        )
    )
    api_mock.get(WIKIDATA_SPARQL).mock(
        return_value=_httpx.Response(200, json=fixtures.OBSCURE_SPARQL)
    )
    api_mock.get(COMMONS_API).mock(side_effect=commons_handler(fixtures.COMMONS_FIXTURES))

    events = await collect_events(qid=fixtures.OBSCURE_QID)
    profile = events[-1].payload

    assert profile["university"]["commons_category"] is None
    assert profile["university"]["coordinates"] is None
    # Раньше здесь был пустой профиль: оба сборщика молчали.
    assert profile["stats"]["found"] > 0, "поиск по названию обязан что-то найти"

    found = [*profile["verified"], *profile["needs_review"]]
    assert found, "фото должно пройти оценку, а не отсеяться"
    assert any("commons_search" in p["source_kinds"] for p in found)

    # Предупреждения о нехватке данных всё равно должны остаться честными.
    joined = " ".join(profile["warnings"])
    assert "P373" in joined and "P625" in joined


async def test_search_found_photo_is_not_rejected_as_wrong_university(full_mock):
    events = await collect_events(qid=fixtures.QID)
    profile = events[-1].payload
    wrong = [
        p for p in profile["rejected"]
        if p["reject_reason"] == "not_this_university"
        and "commons_search" in p["source_kinds"]
    ]
    assert not wrong, "найденное по названию вуза не может быть «не тем вузом»"


async def test_phash_does_not_download_thumbnails_of_rejected_photos(full_mock, monkeypatch):
    """Самая дорогая часть бюджета — скачивание миниатюр.

    Логотипы, мелочь и файлы без лицензии отсеиваются раньше, поэтому
    хешировать их незачем.
    """
    from app.services import phash

    hashed: list[str] = []
    original = phash.compute_hashes

    async def counting(photos, limit=phash.MAX_DOWNLOADS):
        hashed.extend(p.id for p in photos)
        return await original(photos, limit)

    monkeypatch.setattr(phash, "compute_hashes", counting)

    events = await collect_events(qid=fixtures.QID)
    profile = events[-1].payload

    rejected_ids = {p["id"] for p in profile["rejected"] if p["reject_reason"] != "duplicate"}
    assert rejected_ids, "в фикстурах есть отклонённые файлы"
    assert not (rejected_ids & set(hashed)), "отклонённые файлы не должны качаться ради pHash"

    shown_ids = {p["id"] for p in [*profile["verified"], *profile["needs_review"]]}
    assert set(hashed) <= shown_ids, "качаем только то, что реально показываем"


async def test_verified_event_carries_photos_before_description(full_mock):
    """Фото должны уходить на стадии verified — до похода в LLM (п.7 ТЗ)."""
    events = await collect_events(qid=fixtures.QID)
    verified = next(e for e in events if e.stage is Stage.VERIFIED)

    assert verified.payload is not None, "verified обязан нести готовый профиль"
    assert verified.payload["partial"] is True
    assert verified.payload["description"] is None
    # Набор фото тот же, что и в финальном профиле: описание ничего не меняет.
    done = events[-1].payload
    assert done["partial"] is False
    assert [p["id"] for p in verified.payload["verified"]] == [
        p["id"] for p in done["verified"]
    ]
    assert verified.payload["stats"] == done["stats"]


async def test_first_paint_does_not_wait_for_slow_source(api_mock, monkeypatch):
    """Медленный источник не задерживает первый показ фотографий."""
    import asyncio

    from app.config import get_settings

    monkeypatch.setenv("CAMPUSLENS_FIRST_PAINT_BUDGET", "0.3")
    monkeypatch.setenv("CAMPUSLENS_TOTAL_TIMEOUT", "8")
    get_settings.cache_clear()

    api_mock.get(WIKIDATA_API).mock(return_value=httpx.Response(200, json=fixtures.WBSEARCH))
    api_mock.get(WIKIDATA_SPARQL).mock(return_value=httpx.Response(200, json=fixtures.SPARQL))
    api_mock.get(COMMONS_API).mock(side_effect=commons_handler(fixtures.COMMONS_FIXTURES))

    async def slow_site(*args, **kwargs):
        await asyncio.sleep(3.0)
        return []

    from app.services import officialsite

    monkeypatch.setattr(officialsite, "collect_texts", slow_site)
    monkeypatch.setattr(officialsite, "collect", slow_site)

    first_verified_ms: int | None = None
    events = []
    async for event in stream_profile(qid=fixtures.QID):
        events.append(event)
        if event.stage is Stage.VERIFIED and first_verified_ms is None:
            first_verified_ms = event.elapsed_ms
            assert event.payload is not None
            assert event.payload["partial"] is True

    get_settings.cache_clear()

    assert first_verified_ms is not None, "первый показ обязан случиться"
    # Медленный источник спит 3 с — первый показ должен опередить его заметно.
    assert first_verified_ms < 2000, f"первый показ занял {first_verified_ms} мс"
    # И в конце всё равно приходит полный профиль.
    assert events[-1].stage is Stage.DONE
    assert events[-1].payload["partial"] is False
