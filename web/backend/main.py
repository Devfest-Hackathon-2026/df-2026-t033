"""Minimal upload validation API for Fingerprint Symphony.

Images are processed per request and deliberately not persisted by this app.
Actual fingerprint analysis and audio synthesis remain in the browser.
"""
from __future__ import annotations

import io
import logging

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from PIL import Image, UnidentifiedImageError

MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 24_000_000
MIN_IMAGE_SIDE = 192
MAX_IMAGE_SIDE = 8192
ALLOWED_TYPES = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
}
LABELS = {"A", "B", "C"}

app = FastAPI(title="Fingerprint Symphony - Minimal API", version="0.4.0")
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def error(code: str, message: str, status: int = 400) -> None:
    raise HTTPException(status_code=status, detail={
        "status": "error", "code": code, "message": message,
    })


@app.exception_handler(HTTPException)
async def http_error_handler(_request: Request, exc: HTTPException):
    detail = exc.detail
    if not isinstance(detail, dict) or detail.get("status") != "error":
        detail = {"status": "error", "code": "HTTP_ERROR", "message": "リクエストを処理できませんでした。"}
    return JSONResponse(status_code=exc.status_code, content=detail)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_request: Request, _exc: RequestValidationError):
    return JSONResponse(status_code=422, content={
        "status": "error", "code": "INVALID_REQUEST", "message": "送信データに不足または誤りがあります。",
    })


@app.middleware("http")
async def no_cache(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.get("/api/health")
def health():
    return {
        "status": "ok", "upload_validation": True,
        "fingerprint_analysis": "browser", "music_generation": "browser",
        "image_persisted": False,
    }


@app.post("/api/images/validate")
async def validate_image(
    participant_id: str = Form(...),
    consent: bool = Form(...),
    image: UploadFile = File(...),
):
    # No database, persistent image store, personal identifiers, or image logs.
    try:
        if not consent:
            error("CONSENT_REQUIRED", "指紋画像の送信・利用への同意が必要です。", 403)
        if participant_id not in LABELS:
            error("INVALID_PARTICIPANT", "参加者はA・B・Cから選択してください。")
        if image.content_type not in set(ALLOWED_TYPES.values()):
            error("INVALID_IMAGE_TYPE", "JPEG・PNG・WebPの画像を選んでください。", 415)

        # The parser may spool multipart data to a temporary file; UploadFile.close()
        # releases this temporary resource. Do not call write() on any permanent path.
        payload = await image.read(MAX_IMAGE_BYTES + 1)
        if not payload or len(payload) > MAX_IMAGE_BYTES:
            error("INVALID_IMAGE_SIZE", "画像は10MB以下にしてください。", 413)

        try:
            with Image.open(io.BytesIO(payload)) as img:
                fmt = img.format
                width, height = img.size
                if fmt not in ALLOWED_TYPES or ALLOWED_TYPES[fmt] != image.content_type:
                    error("INVALID_IMAGE_TYPE", "画像の内容と形式が一致しません。", 415)
                if (min(width, height) < MIN_IMAGE_SIDE or
                    max(width, height) > MAX_IMAGE_SIDE or
                    width * height > MAX_IMAGE_PIXELS):
                    error("INVALID_IMAGE_DIMENSIONS", "画像は縦横192〜8192px、総画素数2400万以下にしてください。", 413)
                img.verify()
        except (UnidentifiedImageError, OSError, SyntaxError, ValueError, Image.DecompressionBombError):
            error("INVALID_IMAGE", "画像を読み取れませんでした。撮り直してください。")

        return {
            "status": "accepted", "participant_id": participant_id,
            "image_format": fmt.lower(), "width": width, "height": height,
            "image_persisted": False, "features_extracted": False,
            "next_step": "browser_fingerprint_analysis",
        }
    finally:
        await image.close()
