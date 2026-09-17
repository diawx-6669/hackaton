"""Регистрация, вход и привязка загрузок к аккаунту."""
import io
import json

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.routers import auth as auth_router
from app.routers import uploads as uploads_router
from app.services.auth import UserStore
from app.services.uploads import UploadStore

CREDS = {"email": "student@kbtu.edu.kz", "password": "verysecret123", "name": "Аружан"}


@pytest.fixture(autouse=True)
def stores(tmp_path, monkeypatch):
    users = UserStore(tmp_path / "users.json", secret="test-secret")
    uploads = UploadStore(tmp_path / "uploads")
    monkeypatch.setattr(auth_router, "_store", lambda: users)
    monkeypatch.setattr(uploads_router, "_store", lambda: uploads)
    return users, uploads


def make_jpeg() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (1024, 768), (30, 80, 140)).save(buf, format="JPEG")
    return buf.getvalue()


def test_register_returns_token_and_user(stores):
    with TestClient(app) as client:
        r = client.post("/api/auth/register", json=CREDS)
    assert r.status_code == 201
    body = r.json()
    assert body["token"]
    assert body["user"]["email"] == "student@kbtu.edu.kz"
    assert body["user"]["name"] == "Аружан"
    assert "password" not in json.dumps(body).lower()


def test_password_is_never_stored_in_plain_text(stores):
    users, _ = stores
    with TestClient(app) as client:
        client.post("/api/auth/register", json=CREDS)

    saved = users.path.read_text(encoding="utf-8")
    assert CREDS["password"] not in saved
    assert "$2b$" in saved, "должен лежать bcrypt-хеш"


def test_login_works_and_email_is_case_insensitive(stores):
    with TestClient(app) as client:
        client.post("/api/auth/register", json=CREDS)
        r = client.post(
            "/api/auth/login",
            json={"email": "STUDENT@KBTU.EDU.KZ", "password": CREDS["password"]},
        )
    assert r.status_code == 200
    assert r.json()["user"]["email"] == "student@kbtu.edu.kz"


def test_wrong_password_and_unknown_email_look_identical(stores):
    """Иначе по ответу можно перебрать, какие почты зарегистрированы."""
    with TestClient(app) as client:
        client.post("/api/auth/register", json=CREDS)
        wrong = client.post("/api/auth/login", json={"email": CREDS["email"], "password": "nope12345"})
        unknown = client.post("/api/auth/login", json={"email": "nobody@x.kz", "password": "nope12345"})

    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["detail"] == unknown.json()["detail"]


def test_duplicate_email_rejected(stores):
    with TestClient(app) as client:
        client.post("/api/auth/register", json=CREDS)
        r = client.post("/api/auth/register", json=CREDS)
    assert r.status_code == 409


def test_short_password_rejected(stores):
    with TestClient(app) as client:
        r = client.post("/api/auth/register", json={"email": "a@b.kz", "password": "korot"})
    assert r.status_code == 422


def test_me_requires_valid_token(stores):
    with TestClient(app) as client:
        token = client.post("/api/auth/register", json=CREDS).json()["token"]

        ok = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        no_header = client.get("/api/auth/me")
        # Заголовки HTTP — latin-1, поэтому подделка тоже в ASCII.
        garbage = client.get("/api/auth/me", headers={"Authorization": "Bearer forged.token.value"})

    assert ok.status_code == 200 and ok.json()["name"] == "Аружан"
    assert no_header.status_code == 401
    assert garbage.status_code == 401, "подписанный токен нельзя подделать"


def test_photos_follow_the_account_not_the_device(stores):
    """Вошёл с другого устройства — фотографии на месте."""
    with TestClient(app) as client:
        token = client.post("/api/auth/register", json=CREDS).json()["token"]
        auth = {"Authorization": f"Bearer {token}"}

        client.post(
            "/api/uploads",
            files={"file": ("p.jpg", make_jpeg(), "image/jpeg")},
            headers={**auth, "X-Device-Id": "device-phone-111"},
        )
        # То же устройство, но уже без входа — чужой аноним ничего не видит.
        anon = client.get("/api/uploads", headers={"X-Device-Id": "device-phone-111"}).json()
        # Другое устройство, но тот же аккаунт — фото видно.
        other = client.get("/api/uploads", headers={**auth, "X-Device-Id": "device-tablet-222"}).json()

    assert anon["items"] == []
    assert len(other["items"]) == 1


def test_anonymous_upload_still_works(stores):
    with TestClient(app) as client:
        r = client.post(
            "/api/uploads",
            files={"file": ("p.jpg", make_jpeg(), "image/jpeg")},
            headers={"X-Device-Id": "device-anon-9999"},
        )
        wallet = client.get("/api/wallet", headers={"X-Device-Id": "device-anon-9999"}).json()
    assert r.status_code == 201
    assert wallet["coins"] == 10


def test_expired_or_foreign_token_is_rejected(stores):
    users, _ = stores
    foreign = UserStore(users.path, secret="другой-секрет").issue_token("whoever")
    with TestClient(app) as client:
        r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {foreign}"})
    assert r.status_code == 401, "токен, подписанный другим секретом, принимать нельзя"
