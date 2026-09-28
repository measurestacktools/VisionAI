"""VisionAI — premium AI image analysis app powered by Groq vision models.

Docs verified Sept 2026:
- Endpoint (OpenAI-compatible): https://api.groq.com/openai/v1
- Vision model: qwen/qwen3.8-27b (also qwen/qwen3.6-27b)
- Image input: chat.completions messages with
  content=[{"type":"text","text":...},{"type":"image_url","image_url":{"url": data:...;base64,...}}]
- Limits: max 20MB per image-URL request, max 3 images/request (Qwen 3.8),
  each image counts as 2048 input tokens. Base64 uploads should stay small,
  so we downscale/compress server-side before sending.
"""

import base64
import io
import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from openai import (
    APIConnectionError,
    APIStatusError,
    AuthenticationError,
    OpenAI,
    RateLimitError,
)
from PIL import Image

load_dotenv()

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("visionai")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b").strip() or "qwen/qwen3.8-27b"
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1").strip()
try:
    MAX_IMAGE_MB = float(os.getenv("MAX_IMAGE_MB", "10"))
except ValueError:
    MAX_IMAGE_MB = 10.0
MAX_IMAGE_BYTES = int(MAX_IMAGE_MB * 1024 * 1024)

ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp", "image/gif"}
ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
# Longest side after server-side downscale. Keeps base64 payload small & fast.
MAX_SIDE_PX = 1536

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

app = FastAPI(title="VisionAI", version="1.0.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def _friendly_groq_error(exc: Exception) -> tuple[int, str]:
    """Map SDK / HTTP errors to beginner-friendly messages + status codes."""
    if isinstance(exc, AuthenticationError):
        return 401, (
            "Your Groq API key was rejected. Open your .env file, check GROQ_API_KEY "
            "is correct (no extra spaces or quotes), then restart the app. "
            "Get a free key at https://console.groq.com/keys"
        )
    if isinstance(exc, RateLimitError):
        return 429, (
            "Groq rate limit reached (too many requests or tokens). "
            "Wait about a minute and try again. If it keeps happening, "
            "try a smaller image or check your plan limits at "
            "https://console.groq.com/docs/rate-limits"
        )
    if isinstance(exc, APIConnectionError):
        return 503, (
            "Could not reach the Groq API. Check your internet connection and "
            "try again. If Groq is having an outage, wait a few minutes."
        )
    if isinstance(exc, APIStatusError):
        status = exc.status_code or 502
        detail = ""
        try:
            detail = str(exc.response.json())[:400]
        except Exception:
            detail = str(exc)[:400]
        if status == 400 and "image" in detail.lower():
            return 400, (
                "Groq rejected the image (it may be too large or in an unsupported "
                "format). Try a JPG/PNG under 10MB and try again."
            )
        if status == 404:
            return 502, (
                f"Model '{GROQ_MODEL}' was not found on Groq. It may have been "
                "renamed — check https://console.groq.com/docs/models for the current "
                "vision model and update GROQ_MODEL in your .env file."
            )
        return status, f"Groq API error (HTTP {status}). Details: {detail}"
    return 500, f"Unexpected server error: {str(exc)[:300]}"


def _process_image(raw: bytes) -> tuple[str, int, int]:
    """Validate with Pillow, downscale, re-encode as JPEG. Returns (data_uri, w, h)."""
    try:
        img = Image.open(io.BytesIO(raw))
        img.verify()
    except Exception:
        raise ValueError(
            "That file is not a valid image. Please upload a real JPG, PNG, WEBP or GIF file."
        )
    img = Image.open(io.BytesIO(raw))  # reopen after verify()
    # Flatten transparency / animation to a single RGB frame
    if getattr(img, "is_animated", False):
        img.seek(0)
    if img.mode in ("RGBA", "LA", "PA", "P"):
        bg = Image.new("RGB", img.size, (13, 15, 23))
        alpha = img.convert("RGBA").split()[-1] if "A" in img.getbands() else None
        img = img.convert("RGB")
        if alpha is not None:
            bg.paste(img, mask=alpha)
            img = bg
    elif img.mode != "RGB":
        img = img.convert("RGB")

    w, h = img.size
    longest = max(w, h)
    if longest > MAX_SIDE_PX:
        scale = MAX_SIDE_PX / float(longest)
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
        w, h = img.size

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85, optimize=True)
    jpeg_bytes = buf.getvalue()
    b64 = base64.b64encode(jpeg_bytes).decode("utf-8")
    return f"data:image/jpeg;base64,{b64}", w, h


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/api/status")
def api_status():
    configured = bool(GROQ_API_KEY)
    if configured:
        message = f"Connected — model {GROQ_MODEL} ready."
    else:
        message = (
            "No GROQ_API_KEY found. Copy .env.example to .env, "
            "paste your key from https://console.groq.com/keys, then restart the app."
        )
    return {
        "ok": True,
        "configured": configured,
        "model": GROQ_MODEL,
        "max_image_mb": MAX_IMAGE_MB,
        "message": message,
    }


@app.post("/api/analyze")
async def api_analyze(
    image: UploadFile | None = File(default=None),
    question: str = Form(default=""),
):
    question = (question or "").strip()

    # --- Validate question ---
    if not question:
        return JSONResponse(
            status_code=400,
            content={"error": "Please type a question about the image before analyzing."},
        )
    if len(question) > 2000:
        return JSONResponse(
            status_code=400,
            content={"error": "Your question is too long (max 2000 characters). Please shorten it."},
        )

    # --- Validate upload present ---
    if image is None or not image.filename:
        return JSONResponse(
            status_code=400, content={"error": "Please upload an image first."}
        )

    # --- Validate type ---
    mime = (image.content_type or "").lower().split(";")[0].strip()
    ext = os.path.splitext(image.filename or "")[1].lower()
    if (mime and mime not in ALLOWED_MIME) or (ext and ext not in ALLOWED_EXT):
        # Fall back: if mime missing, judge by extension (and vice versa)
        if ext not in ALLOWED_EXT and mime not in ALLOWED_MIME:
            return JSONResponse(
                status_code=400,
                content={
                    "error": (
                        f"Unsupported file type '{image.filename}'. "
                        "Please upload a JPG, PNG, WEBP or GIF image."
                    )
                },
            )

    # --- Validate size ---
    raw = await image.read()
    if not raw:
        return JSONResponse(
            status_code=400, content={"error": "The uploaded file is empty. Try another image."}
        )
    if len(raw) > MAX_IMAGE_BYTES:
        mb = len(raw) / (1024 * 1024)
        return JSONResponse(
            status_code=413,
            content={
                "error": (
                    f"Image is too large ({mb:.1f}MB — limit is {MAX_IMAGE_MB:g}MB). "
                    "Please compress/resize it or choose a smaller file."
                )
            },
        )

    # --- Decode / normalize image ---
    try:
        data_uri, width, height = _process_image(raw)
    except ValueError as ve:
        return JSONResponse(status_code=400, content={"error": str(ve)})

    # --- API key check ---
    if not GROQ_API_KEY:
        return JSONResponse(
            status_code=401,
            content={
                "error": (
                    "No GROQ_API_KEY configured. Copy .env.example to .env, add your key "
                    "from https://console.groq.com/keys, then restart the app with: "
                    "uvicorn app:app --reload"
                )
            },
        )

    # --- Call Groq via OpenAI-compatible endpoint ---
    try:
        client = OpenAI(api_key=GROQ_API_KEY, base_url=GROQ_BASE_URL)
        completion = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are VisionAI, a precise visual-analysis assistant. "
                        "Answer the user's question about the image directly, with concrete "
                        "details you can see. If text is visible and asked for, transcribe it "
                        "accurately. If unsure, say so instead of guessing. "
                        "Format with short paragraphs and bullet points where helpful."
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": question},
                        {"type": "image_url", "image_url": {"url": data_uri}},
                    ],
                },
            ],
            max_tokens=1024,
            temperature=0.7,
        )
        answer = (completion.choices[0].message.content or "").strip()
        if not answer:
            return JSONResponse(
                status_code=502,
                content={"error": "The AI returned an empty response. Please try again."},
            )
        usage = None
        try:
            u = completion.usage
            if u is not None:
                usage = {
                    "prompt_tokens": getattr(u, "prompt_tokens", None),
                    "completion_tokens": getattr(u, "completion_tokens", None),
                    "total_tokens": getattr(u, "total_tokens", None),
                }
        except Exception:
            usage = None
        return {
            "answer": answer,
            "model": GROQ_MODEL,
            "image": {"width": width, "height": height},
            "usage": usage,
        }
    except Exception as exc:  # mapped to friendly messages below
        log.exception("Groq request failed")
        status, msg = _friendly_groq_error(exc)
        return JSONResponse(status_code=status, content={"error": msg})


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("app:app", host="127.0.0.1", port=port, reload=True)
