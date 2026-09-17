"""Сайт закрыт входом: без аккаунта поиск, профиль и сравнение недоступны."""
import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers import auth as auth_router
from app.services.auth import UserStore
from tests import fixtures
from tests.conftest import COMMONS_API, WIKIDATA_API, WIKIDATA_SPARQL, commons_handler

CLOSED = ["/api/resolve?q=КБТУ", "/api/profile?q=КБТУ", "/api/profile.json?q=КБТУ",
          "/api/compare?a=КБТУ&b=КазНУ"]


@pytest.fixture
def gated(tmp_path, monkeypatch):
    """Включаем требование входа обратно — по умолчанию оно выключено в conftest."""
    monkeypatch.setenv("CAMPUSLENS_REQUIRE_AUTH", "true")
    from app.config import get_settings

    get_settings.cache_clear()
    store = UserStore(tmp_path / "users.json", secret="gate-secret")
    monkeypatch.setattr(auth_router, "_store", lambda: store)
    yield store
    get_settings.cache_clear()


@pytest.mark.parametrize("path", CLOSED)
def test_endpoint_requires_login(gated, path):
    with TestClient(app) as client:
        r = client.get(path)
    assert r.status_code == 401
    assert "вход" in r.json()["detail"].lower()


def test_garbage_token_does_not_open_the_door(gated):
    with TestClient(app) as client:
        r = client.get("/api/resolve?q=КБТУ", headers={"Authorization": "Bearer forged"})
    assert r.status_code == 401


def test_logged_in_user_gets_results(gated, api_mock):
    api_mock.get(WIKIDATA_API).mock(return_value=httpx.Response(200, json=fixtures.WBSEARCH))
    api_mock.get(WIKIDATA_SPARQL).mock(return_value=httpx.Response(200, json=fixtures.SPARQL))
    api_mock.get(COMMONS_API).mock(side_effect=commons_handler(fixtures.COMMONS_FIXTURES))

    with TestClient(app) as client:
        token = client.post(
            "/api/auth/register",
            json={"email": "jury@locus.kz", "password": "juryjury123"},
        ).json()["token"]

        r = client.get("/api/resolve?q=КБТУ", headers={"Authorization": f"Bearer {token}"})

    assert r.status_code == 200
    assert r.json()["candidates"]


def test_health_and_auth_stay_open(gated):
    """Иначе не войти и не проверить, что сервис жив."""
    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200
        # Регистрация и вход не могут требовать входа.
        assert client.post("/api/auth/login", json={"email": "a@b.kz", "password": "x"}).status_code == 401
        assert client.get("/api/auth/me").status_code == 401
