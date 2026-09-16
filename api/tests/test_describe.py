"""Описание кампуса: LLM не должна протащить ни одного факта без источника."""
import json
from types import SimpleNamespace

import pytest

from app.models import Coordinates, Photo, PhotoCategory, SourceKind, University
from app.services import describe


def uni() -> University:
    return University(
        id="Q1798175",
        name="Казахстанско-Британский технический университет",
        description="университет в Алматы",
        city="Алматы",
        country="Казахстан",
        inception="1998-01-01",
        website="https://kbtu.edu.kz/",
        coordinates=Coordinates(lat=43.236, lon=76.929),
        wikidata_url="https://www.wikidata.org/wiki/Q1798175",
    )


def photo(pid: str, description: str, category=PhotoCategory.CAMPUS) -> Photo:
    return Photo(
        id=pid,
        title=pid,
        url=f"https://upload.wikimedia.org/{pid}",
        source_page_url=f"https://commons.wikimedia.org/wiki/File:{pid}",
        source_kinds=[SourceKind.COMMONS_CATEGORY],
        description=description,
        category=category,
    )


def test_facts_come_only_from_our_pipeline():
    facts = describe.build_facts(uni(), [photo("a.jpg", "Главный корпус")])
    ids = {f["id"] for f in facts}
    assert {"wd-name", "wd-city", "wd-inception", "wd-site"} <= ids
    assert "photo-a.jpg" in ids
    # У каждого факта есть ссылка — иначе его нечем подтвердить.
    assert all(f["url"].startswith("http") for f in facts)


def test_claim_with_unknown_source_is_dropped():
    facts = describe.build_facts(uni(), [photo("a.jpg", "Главный корпус")])
    raw = {
        "summary": "Кампус расположен в Алматы. В вузе учится 20 000 студентов.",
        "claims": [
            {"claim": "Кампус расположен в Алматы", "source_id": "wd-city"},
            # Источника с таким id мы не давали — число выдумано.
            {"claim": "В вузе учится 20 000 студентов", "source_id": "wd-students"},
        ],
        "insufficient_data": False,
    }
    result = describe._validate(raw, facts)

    assert [c["claim"] for c in result.claims] == ["Кампус расположен в Алматы"]
    assert result.unverified_claims == ["В вузе учится 20 000 студентов"]


def test_description_without_any_valid_claim_is_marked_insufficient():
    facts = describe.build_facts(uni(), [])
    raw = {
        "summary": "Прекрасный современный кампус мирового уровня.",
        "claims": [{"claim": "мирового уровня", "source_id": "выдумка"}],
        "insufficient_data": False,
    }
    result = describe._validate(raw, facts)
    assert result.insufficient_data is True, "без подтверждённых утверждений описанию верить нельзя"
    assert result.claims == []


def test_valid_claims_carry_source_url():
    facts = describe.build_facts(uni(), [photo("a.jpg", "Главный корпус")])
    raw = {
        "summary": "Вуз основан в 1998 году.",
        "claims": [{"claim": "Вуз основан в 1998 году", "source_id": "wd-inception"}],
        "insufficient_data": False,
    }
    result = describe._validate(raw, facts)
    assert result.claims[0]["url"] == "https://www.wikidata.org/wiki/Q1798175"
    assert result.sources and result.sources[0]["id"] == "wd-inception"


async def test_without_any_api_key_description_is_skipped(monkeypatch):
    for var in ("ANTHROPIC_API_KEY", "GOOGLE_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    from app.config import get_settings

    get_settings.cache_clear()
    assert await describe.describe(uni(), [photo("a.jpg", "Главный корпус")]) is None
    get_settings.cache_clear()


@pytest.fixture
def fake_llm(monkeypatch):
    """Подменяем SDK: настоящий ключ для теста не нужен."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    from app.config import get_settings

    get_settings.cache_clear()

    captured: dict = {}

    def install(payload: dict, stop_reason: str = "end_turn"):
        class FakeMessages:
            async def create(self, **kwargs):
                captured.update(kwargs)
                return SimpleNamespace(
                    stop_reason=stop_reason,
                    content=[SimpleNamespace(type="text", text=json.dumps(payload, ensure_ascii=False))],
                )

        class FakeClient:
            def __init__(self, *a, **kw):
                self.beta = SimpleNamespace(messages = FakeMessages())

        import anthropic

        monkeypatch.setattr(anthropic, "AsyncAnthropic", FakeClient)

    yield install, captured
    get_settings.cache_clear()


async def test_prompt_contains_only_our_facts(fake_llm):
    install, captured = fake_llm
    install({
        "summary": "Вуз находится в Алматы.",
        "claims": [{"claim": "Вуз находится в Алматы", "source_id": "wd-city"}],
        "insufficient_data": False,
    })

    result = await describe.describe(uni(), [photo("a.jpg", "Главный корпус")])
    assert result is not None
    assert result.summary == "Вуз находится в Алматы."
    assert result.model == "claude-opus-5"

    prompt = captured["messages"][0]["content"]
    assert "[wd-city]" in prompt and "[photo-a.jpg]" in prompt
    assert "Другого источника у тебя нет" in prompt
    # Структурированный ответ обязателен — иначе цитаты не проверить.
    assert captured["output_config"]["format"]["type"] == "json_schema"


async def test_refusal_is_handled_without_breaking_profile(fake_llm):
    install, _ = fake_llm
    install({"summary": "", "claims": [], "insufficient_data": True}, stop_reason="refusal")
    assert await describe.describe(uni(), [photo("a.jpg", "Корпус")]) is None


async def test_broken_llm_response_returns_none(fake_llm, monkeypatch):
    install, _ = fake_llm
    install({"summary": "ок", "claims": [], "insufficient_data": False})

    import anthropic

    class Boom:
        def __init__(self, *a, **kw):
            self.beta = SimpleNamespace(messages=SimpleNamespace())

        pass

    class FailingMessages:
        async def create(self, **kwargs):
            raise RuntimeError("api down")

    class FailingClient:
        def __init__(self, *a, **kw):
            self.beta = SimpleNamespace(messages=FailingMessages())

    monkeypatch.setattr(anthropic, "AsyncAnthropic", FailingClient)
    # Упавшая LLM не должна ронять сборку профиля.
    assert await describe.describe(uni(), [photo("a.jpg", "Корпус")]) is None


# --- провайдер Gemini ---

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent"


def gemini_response(payload: dict) -> dict:
    """Ответ Gemini: структурированный JSON лежит текстом внутри parts."""
    return {
        "candidates": [
            {"content": {"parts": [{"text": json.dumps(payload, ensure_ascii=False)}]}}
        ]
    }


@pytest.fixture
def gemini_env(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    from app.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


async def test_gemini_is_picked_when_google_key_is_set(gemini_env, api_mock):
    import httpx

    route = api_mock.post(GEMINI_URL).mock(
        return_value=httpx.Response(
            200,
            json=gemini_response({
                "summary": "Вуз основан в 1998 году.",
                "claims": [{"claim": "Вуз основан в 1998 году", "source_id": "wd-inception"}],
                "insufficient_data": False,
            }),
        )
    )

    result = await describe.describe(uni(), [photo("a.jpg", "Главный корпус")])
    assert result is not None
    assert result.model == "gemini-3.6-flash"
    assert result.claims[0]["source_id"] == "wd-inception"

    # Ключ уходит параметром запроса, а не в теле.
    assert route.calls.last.request.url.params["key"] == "test-key"
    body = json.loads(route.calls.last.request.content)
    assert body["generationConfig"]["responseMimeType"] == "application/json"
    assert "[wd-inception]" in body["contents"][0]["parts"][0]["text"]


async def test_gemini_hallucination_is_dropped_too(gemini_env, api_mock):
    import httpx

    api_mock.post(GEMINI_URL).mock(
        return_value=httpx.Response(
            200,
            json=gemini_response({
                "summary": "Кампус в Алматы. Здесь 15 корпусов.",
                "claims": [
                    {"claim": "Кампус в Алматы", "source_id": "wd-city"},
                    {"claim": "Здесь 15 корпусов", "source_id": "wd-buildings"},
                ],
                "insufficient_data": False,
            }),
        )
    )
    result = await describe.describe(uni(), [photo("a.jpg", "Корпус")])
    assert [c["claim"] for c in result.claims] == ["Кампус в Алматы"]
    assert result.unverified_claims == ["Здесь 15 корпусов"]


async def test_gemini_error_does_not_break_profile(gemini_env, api_mock):
    import httpx

    api_mock.post(GEMINI_URL).mock(return_value=httpx.Response(429, json={"error": "rate limit"}))
    assert await describe.describe(uni(), [photo("a.jpg", "Корпус")]) is None


async def test_gemini_empty_candidates_returns_none(gemini_env, api_mock):
    import httpx

    api_mock.post(GEMINI_URL).mock(return_value=httpx.Response(200, json={"candidates": []}))
    assert await describe.describe(uni(), [photo("a.jpg", "Корпус")]) is None


async def test_explicit_provider_wins_over_autodetect(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "g")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "a")
    monkeypatch.setenv("CAMPUSLENS_LLM_PROVIDER", "anthropic")
    from app.config import get_settings

    get_settings.cache_clear()
    assert get_settings().active_llm == ("anthropic", "a")
    get_settings.cache_clear()


# --- провайдер Groq ---
#
# ВАЖНО: живой вызов к api.groq.com из окружения разработки заблокирован,
# поэтому проверен весь код вокруг запроса, но не сам сетевой вызов.
# Первый запуск с настоящим ключом нужно проверить руками.

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


def groq_response(payload: dict) -> dict:
    return {"choices": [{"message": {"content": json.dumps(payload, ensure_ascii=False)}}]}


@pytest.fixture
def groq_env(monkeypatch):
    for var in ("ANTHROPIC_API_KEY", "GOOGLE_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    from app.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


async def test_groq_request_shape(groq_env, api_mock):
    import httpx

    route = api_mock.post(GROQ_URL).mock(
        return_value=httpx.Response(
            200,
            json=groq_response({
                "summary": "Вуз в Алматы.",
                "claims": [{"claim": "Вуз в Алматы", "source_id": "wd-city"}],
                "insufficient_data": False,
            }),
        )
    )

    result = await describe.describe(uni(), [photo("a.jpg", "Корпус")])
    assert result is not None
    assert result.model == "llama-3.3-70b-versatile"

    request = route.calls.last.request
    assert request.headers["authorization"] == "Bearer gsk_test"
    body = json.loads(request.content)
    assert body["response_format"] == {"type": "json_object"}
    # Схему обязаны продиктовать текстом: json_schema поддерживают не все модели.
    assert "insufficient_data" in body["messages"][0]["content"]
    assert "[wd-city]" in body["messages"][1]["content"]


async def test_groq_hallucination_is_dropped(groq_env, api_mock):
    import httpx

    api_mock.post(GROQ_URL).mock(
        return_value=httpx.Response(
            200,
            json=groq_response({
                "summary": "Кампус в Алматы. Здесь 40 лабораторий.",
                "claims": [
                    {"claim": "Кампус в Алматы", "source_id": "wd-city"},
                    {"claim": "Здесь 40 лабораторий", "source_id": "wd-labs"},
                ],
                "insufficient_data": False,
            }),
        )
    )
    result = await describe.describe(uni(), [photo("a.jpg", "Корпус")])
    assert [c["claim"] for c in result.claims] == ["Кампус в Алматы"]
    assert result.unverified_claims == ["Здесь 40 лабораторий"]


async def test_groq_retired_model_error_does_not_break_profile(groq_env, api_mock):
    """Groq регулярно выводит модели из обращения — это не должно ронять профиль."""
    import httpx

    api_mock.post(GROQ_URL).mock(
        return_value=httpx.Response(
            404, json={"error": {"message": "The model `llama-x` has been decommissioned"}}
        )
    )
    assert await describe.describe(uni(), [photo("a.jpg", "Корпус")]) is None


async def test_groq_model_is_configurable(monkeypatch, groq_env, api_mock):
    import httpx

    monkeypatch.setenv("CAMPUSLENS_GROQ_MODEL", "openai/gpt-oss-120b")
    from app.config import get_settings

    get_settings.cache_clear()

    route = api_mock.post(GROQ_URL).mock(
        return_value=httpx.Response(
            200,
            json=groq_response({
                "summary": "Вуз в Алматы.",
                "claims": [{"claim": "Вуз в Алматы", "source_id": "wd-city"}],
                "insufficient_data": False,
            }),
        )
    )
    await describe.describe(uni(), [photo("a.jpg", "Корпус")])
    assert json.loads(route.calls.last.request.content)["model"] == "openai/gpt-oss-120b"
    get_settings.cache_clear()


async def test_gemini_wins_over_groq_in_auto_mode(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "g")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_x")
    monkeypatch.delenv("CAMPUSLENS_LLM_PROVIDER", raising=False)
    from app.config import get_settings

    get_settings.cache_clear()
    assert get_settings().active_llm[0] == "gemini"
    get_settings.cache_clear()
