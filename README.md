# VisionAI — See more in every image

VisionAI is a polished, ready-to-run **AI image analysis app**. Upload any photo, screenshot, or document, ask a question about it, and get an instant AI-powered visual analysis — running on Groq's ultra-fast inference.

No database. No frontend framework. No fake responses. Just a clean FastAPI backend + a premium dark interface + your own Groq API key.

## Tech stack

- Backend: Python + FastAPI (`app.py`), served with uvicorn
- AI: Groq vision models via the OpenAI-compatible API (`https://api.groq.com/openai/v1`)
- Image handling: Pillow validation, server-side downscale/compress, base64 data-URI input
- Frontend: dependency-free HTML/CSS/vanilla JS in `static/`

## Features

- Drag-and-drop image upload with live preview, file info, and remove button
- Custom question box + one-click suggested prompts (describe, read text, key details)
- Real AI visual analysis via Groq vision models (OpenAI-compatible API)
- Premium dark UI: glass panels, gradients, responsive desktop + mobile
- Loading shimmer, empty state, and beginner-friendly error states
- Copy-answer button, clear/reset, character counter
- Live API connection status pill in the header
- Server-side validation: file type, file size, empty question, image integrity
- Automatic image downscale/compress so uploads stay fast and within Groq limits
- API key stays on your server — typed into your own local page, kept only in server memory or your local `.env`; never in browser storage, never sent back to the browser, never committed to git

## Requirements

- Python 3.10 or newer
- A free Groq API key (takes ~2 minutes)
- Internet connection (the AI call goes to Groq's API)

## Setup — installation

```bash
cd VisionAI
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
# source .venv/bin/activate

pip install -r requirements.txt
```

## Creating a Groq API key (free)

1. Go to **https://console.groq.com/keys**
2. Sign up / log in (free tier is enough for this project)
3. Click **Create API Key**
4. Copy the key — it starts with `gsk_...`

## Setting your API key (pick either option)

**Option A — Settings panel (easiest, no code):**

1. Run the app and open http://127.0.0.1:8000
2. Click **Settings** (top right)
3. Paste your key, click **Save key** — it's verified instantly

The key is kept only in the server's memory: it's never written to disk, never logged, and never shown again. It clears when the server restarts. Use **Remove** in Settings to forget it at any time.

**Option B — `.env` file (permanent):**

```bash
# Windows
copy .env.example .env

# macOS / Linux
cp .env.example .env
```

Then open `.env` in any text editor and paste your key:

```
GROQ_API_KEY=gsk_paste_your_key_here
GROQ_MODEL=qwen/qwen3.8-27b
```

> The default model `qwen/qwen3.8-27b` is the current vision-capable model (verified from https://console.groq.com/docs/vision). Note Groq lists it as a **preview** model, which means Groq can rename or retire it on short notice — if you ever see a "model was not found" error, check https://console.groq.com/docs/models for the current vision model and update `GROQ_MODEL`.

## Running the application

```bash
uvicorn app:app --reload
```

Then open **http://127.0.0.1:8000** in your browser.

- Homepage: `GET /`
- Health check: `GET /api/status` (shows whether your key is configured and where it came from)
- Save key: `POST /api/key` (JSON `{"key": "..."}` — verified with Groq, kept in server memory only)
- Remove key: `DELETE /api/key` (forgets the Settings key; falls back to `.env`)
- Analysis: `POST /api/analyze` (multipart: `image` file + `question` text)

## How the project works

```
Browser (static/index.html + app.js)
   │  FormData { image, question }
   ▼
FastAPI (app.py)
   │  1. validates question, file type, file size
   │  2. verifies the image with Pillow, downscales to max 1536px, re-encodes as JPEG
   │  3. base64-encodes it into a data: URI
   │  4. calls Groq via the OpenAI SDK (base_url=https://api.groq.com/openai/v1)
   │     messages = [system prompt, {text: question, image_url: data_uri}]
   ▼
Groq vision model (qwen/qwen3.8-27b) → answer text → JSON back to the browser
```

Key files:

| File | Purpose |
|---|---|
| `app.py` | FastAPI backend, validation, Groq call |
| `static/index.html` | Page structure |
| `static/styles.css` | Premium dark theme |
| `static/app.js` | Upload, status check, analyze, copy, errors |
| `.env.example` | Template for your config |
| `requirements.txt` | Python dependencies |

## How to customize it

- **Change the model:** set `GROQ_MODEL` in `.env` (e.g. `qwen/qwen3.6-27b`).
- **Change the personality:** edit the `system` prompt in `app.py` (`api_analyze`).
- **Longer answers:** raise `max_tokens=1024` in `app.py`.
- **Bigger uploads:** raise `MAX_IMAGE_MB` in `.env` (keep ≤ 10–15MB; Groq caps image requests at 20MB and base64 inflates size ~33%).
- **Suggested prompts:** edit the `.chip` buttons in `static/index.html`.
- **Theme:** tweak the CSS variables at the top of `static/styles.css`.
- **Port:** run `uvicorn app:app --reload --port 8000` (or set `PORT` in `.env` when starting via `python app.py`).

## Limitations

- Single image per request; very large images are downscaled server-side before analysis
- Answers capped at ~1024 tokens; very small/low-quality images may yield uncertain results
- English-first prompts; other languages work but less precisely
- No chat history — each analysis is a single independent request

## Troubleshooting — common errors

| Message | What to do |
|---|---|
| `No API key configured` | Click **Settings** (top right) and paste your key, or set up `.env` as above. |
| `Your Groq API key was rejected` | Key is wrong or has extra spaces/quotes. Re-copy from https://console.groq.com/keys. |
| `Image is too large` | Use a smaller file or compress it (JPG quality 80, max ~2000px wide). |
| `Unsupported file type` | Only JPG, PNG, WEBP, GIF are accepted. |
| `Groq rate limit reached` | Free tier quota hit — wait ~1 minute and retry. |
| `Model ... was not found` | Groq renamed the model. Check https://console.groq.com/docs/models and update `GROQ_MODEL`. |
| `Could not reach the Groq API` | No internet, or Groq is down. Check your connection and try again. |

## Security warning

- Your `.env` file contains a **secret API key**. Never share it, never commit it, never paste it into screenshots or videos.
- `.gitignore` already excludes `.env`. Keep it that way.
- The Settings-panel key only lives in the server's memory (`app.py`): it is never written to disk, never logged, never stored in the browser, and never sent back to any page. It disappears when the server restarts.
- If a key ever leaks, delete it at https://console.groq.com/keys and create a new one.
