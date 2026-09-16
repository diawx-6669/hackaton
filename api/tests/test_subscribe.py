import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers import subscribe as subscribe_router
from app.services.subscriptions import SubscriptionStore


@pytest.fixture(autouse=True)
def store(tmp_path, monkeypatch):
    """Каждый тест — со своим файлом заявок, ничего не пишем в репозиторий."""
    s = SubscriptionStore(tmp_path / "subs.json")
    monkeypatch.setattr(subscribe_router, "_store", lambda: s)
    return s


def test_subscribe_saves_request(store):
    with TestClient(app) as client:
        r = client.post(
            "/api/subscribe",
            json={"email": "student@example.com", "university": "Aktobe Regional University"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["queue_size"] == 1

    saved = json.loads(store.path.read_text(encoding="utf-8"))
    assert saved[0]["email"] == "student@example.com"
    assert saved[0]["university"] == "Aktobe Regional University"
    assert saved[0]["created_at"]


def test_no_mail_provider_is_reported_honestly(store):
    """Нельзя обещать письмо, если рассылка не настроена."""
    with TestClient(app) as client:
        r = client.post(
            "/api/subscribe", json={"email": "a@example.com", "university": "Тестовый вуз"}
        )
    body = r.json()
    assert body["delivery"] == "stored_only"
    assert "не подключена" in body["message"]


def test_duplicate_request_is_not_stored_twice(store):
    payload = {"email": "dup@example.com", "university": "КБТУ"}
    with TestClient(app) as client:
        first = client.post("/api/subscribe", json=payload).json()
        second = client.post("/api/subscribe", json={**payload, "email": "DUP@example.com"}).json()
    assert first["queue_size"] == 1
    assert second["queue_size"] == 1


def test_invalid_email_rejected():
    with TestClient(app) as client:
        r = client.post("/api/subscribe", json={"email": "не-почта", "university": "КБТУ"})
    assert r.status_code == 422


def test_university_name_required():
    with TestClient(app) as client:
        r = client.post("/api/subscribe", json={"email": "a@example.com", "university": "x"})
    assert r.status_code == 422
