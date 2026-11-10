import io
import sys
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from main import app

client = TestClient(app)


def photo(mode="RGB", fmt="JPEG", size=(240, 260)):
    data = io.BytesIO()
    Image.new(mode, size, color="white").save(data, format=fmt)
    return data.getvalue()


def post(data=None, raw=None, content_type="image/jpeg"):
    return client.post(
        "/api/images/validate",
        data=data if data is not None else {"participant_id": "A", "consent": "true"},
        files={"image": ("fingerprint.jpg", raw if raw is not None else photo(), content_type)},
    )


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["image_persisted"] is False
    assert r.headers["cache-control"] == "no-store"


def test_valid_jpeg_and_png():
    r = post()
    assert r.status_code == 200, r.text
    assert r.json()["participant_id"] == "A"
    assert r.json()["features_extracted"] is False
    png = post({"participant_id": "B", "consent": "true"}, photo(fmt="PNG"), "image/png")
    assert png.status_code == 200
    assert png.json()["image_format"] == "png"


def test_consent_and_participant():
    assert post({"participant_id": "A", "consent": "false"}).status_code == 403
    assert post({"participant_id": "X", "consent": "true"}).status_code == 400


def test_invalid_image_type_and_bytes():
    assert post(raw=b"not a photo").status_code == 400
    assert post(content_type="text/plain").status_code == 415
    assert post(raw=photo(fmt="PNG"), content_type="image/jpeg").status_code == 415


def test_image_size_limit_and_dimensions():
    assert post(raw=b"x" * (10 * 1024 * 1024 + 1)).status_code == 413
    assert post(raw=photo(size=(100, 200))).status_code == 413


def test_missing_fields_without_sensitive_echo():
    r = client.post("/api/images/validate", data={"participant_id": "A"}, files={"image": ("x.jpg", photo(), "image/jpeg")})
    assert r.status_code == 422
    assert "image" not in r.json()["message"].lower()
