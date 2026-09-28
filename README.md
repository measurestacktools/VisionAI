# VisionAI — See more in every image

VisionAI is a polished, ready-to-run **AI image analysis app**. Upload any photo, screenshot, or document, ask a question about it, and get an instant AI-powered visual analysis — running on Groq's ultra-fast inference.

No database. No frontend framework. No fake responses. Just a clean FastAPI backend + a premium dark SaaS interface + your own Groq API key.

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
- API key stays server-side — never exposed to the browser

## Requirements

- Python 3.10 or newer
- A free Groq API key (takes ~2 minutes)
- Internet connection (the AI call goes to Groq's API)

## Installation

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

## Configuring `.env`

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

> The default model `qwen/qwen3.8-27b` is the current vision-capable model (verified Sept 2026 from https://console.groq.com/docs/vision). If Groq renames models in the future, check https://console.groq.com/docs/models and update `GROQ_MODEL`.

## Running the application

```bash
uvicorn app:app --reload
```

Then open **http://127.0.0.1:8000** in your browser.

- Homepage: `GET /`
- Health check: `GET /api/status` (shows whether your key is configured)
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
- **Port:** set `PORT` in `.env` and run `uvicorn app:app --port 8001 --reload`.

## Common errors

| Message | What to do |
|---|---|
| `No GROQ_API_KEY configured` | You didn't create `.env` yet. Copy `.env.example` → `.env`, paste your key, restart the server. |
| `Your Groq API key was rejected` | Key is wrong or has extra spaces/quotes. Re-copy from https://console.groq.com/keys. |
| `Image is too large` | Use a smaller file or compress it (JPG quality 80, max ~2000px wide). |
| `Unsupported file type` | Only JPG, PNG, WEBP, GIF are accepted. |
| `Groq rate limit reached` | Free tier quota hit — wait ~1 minute and retry. |
| `Model ... was not found` | Groq renamed the model. Check https://console.groq.com/docs/models and update `GROQ_MODEL`. |
| `Could not reach the Groq API` | No internet, or Groq is down. Check your connection and try again. |

## Security warning

- Your `.env` file contains a **secret API key**. Never share it, never commit it, never paste it into screenshots or videos.
- `.gitignore` already excludes `.env`. Keep it that way.
- The key only lives on your server (`app.py`) — the frontend JavaScript never sees it.
- If a key ever leaks, delete it at https://console.groq.com/keys and create a new one.
