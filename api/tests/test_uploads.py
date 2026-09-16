"""Загрузка фото студентами и бонусы."""
import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.routers import uploads as uploads_router
from app.services.uploads import UploadStore

DEVICE = "device-abc12345"


def make_jpeg(size=(1280, 960), with_gps=False) -> bytes:
    img = Image.new("RGB", size, (40, 90, 160))
    buf = io.BytesIO()
    if with_gps:
        exif = Image.Exif()
        exif[0x8825] = {1: "N", 2: (43.0, 14.0, 9.0), 3: "E", 4: (76.0, 55.0, 44.0)}
        img.save(buf, format="JPEG", exif=exif)
    else:
        img.save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture(autouse=True)
def store(tmp_path, monkeypatch):
    s = UploadStore(tmp_path / "uploads")
    monkeypatch.setattr(uploads_router, "_store", lambda: s)
    return s


def post(client, content=None, device=DEVICE, content_type="image/jpeg", **form):
    return client.post(
        "/api/uploads",
        files={"file": ("photo.jpg", content if content is not None else make_jpeg(), content_type)},
        headers={"X-Device-Id": device},
        data=form,
    )


def test_upload_returns_record_and_coins(store):
    with TestClient(app) as client:
        r = post(client, university_name="КБТУ", caption="Главный корпус")
    assert r.status_code == 201
    body = r.json()
    assert body["coins"] == 10
    assert body["caption"] == "Главный корпус"
    assert body["university_name"] == "КБТУ"
    assert body["url"].startswith("/api/uploads/")
    assert body["width"] == 1280


def test_uploaded_file_is_served_back(store):
    with TestClient(app) as client:
        url = post(client).json()["url"]
        got = client.get(url)
    assert got.status_code == 200
    assert got.headers["content-type"] == "image/jpeg"


def test_exif_is_stripped_but_geotag_flag_is_kept(store):
    with TestClient(app) as client:
        body = post(client, content=make_jpeg(with_gps=True)).json()
        raw = client.get(body["url"]).content

    # Геотег зафиксирован как улика...
    assert body["has_geotag"] is True
    # ...но сам EXIF из отданного файла вычищен: не раздаём координаты и камеру.
    saved = Image.open(io.BytesIO(raw))
    assert not saved.getexif().get_ifd(0x8825)


def test_wallet_counts_only_own_photos(store):
    with TestClient(app) as client:
        post(client, device="device-aaaa1111")
        post(client, device="device-aaaa1111")
        post(client, device="device-bbbb2222")

        mine = client.get("/api/wallet", headers={"X-Device-Id": "device-aaaa1111"}).json()
        other = client.get("/api/wallet", headers={"X-Device-Id": "device-bbbb2222"}).json()

    assert mine == {"photos": 2, "coins": 20, "per_photo": 10}
    assert other["coins"] == 10


def test_my_uploads_lists_newest_first_and_only_mine(store):
    with TestClient(app) as client:
        post(client, device="device-aaaa1111", caption="первое")
        post(client, device="device-bbbb2222", caption="чужое")
        post(client, device="device-aaaa1111", caption="второе")

        items = client.get("/api/uploads", headers={"X-Device-Id": "device-aaaa1111"}).json()["items"]

    assert [i["caption"] for i in items] == ["второе", "первое"]


def test_non_image_is_rejected(store):
    with TestClient(app) as client:
        r = post(client, content=b"not an image at all", content_type="application/pdf")
    assert r.status_code == 422
    assert "JPEG" in r.json()["detail"]


def test_tiny_image_is_rejected_with_reason(store):
    with TestClient(app) as client:
        r = post(client, content=make_jpeg(size=(200, 150)))
    assert r.status_code == 422
    assert "маленькое" in r.json()["detail"]


def test_device_header_is_required(store):
    with TestClient(app) as client:
        r = client.post("/api/uploads", files={"file": ("p.jpg", make_jpeg(), "image/jpeg")})
    assert r.status_code == 400
    assert "X-Device-Id" in r.json()["detail"]


def test_bad_device_id_is_rejected(store):
    with TestClient(app) as client:
        r = post(client, device="../etc")
    assert r.status_code == 400


def test_path_traversal_in_filename_is_blocked(store):
    with TestClient(app) as client:
        r = client.get("/api/uploads/..%2F..%2Findex.json")
    assert r.status_code == 404
