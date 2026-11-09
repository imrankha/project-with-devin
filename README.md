# Hifz Helper – Quran Memorization Web App

A small web application (Python + HTML/CSS/JS) that helps you memorize the Quran ayah by ayah.

## Features

- **Surah → Ayah selection**: pick any of the 114 surahs, then pick an ayah.
- **Ayah view**: Uthmani Arabic text with **English, Hindi and Urdu** translations and verse audio (Mishari al-Afasy).
- **Word-by-word meanings**: each word with transliteration and English / Hindi / Urdu meaning (tap a word to hear it).
- **Reading counter**: tap *I read it (+1)* after each reading. You need **25 readings** before recitation is unlocked (enforced on the server).
- **Recite from memory**: the Arabic text is hidden, you recite using the microphone (Web Speech API, Arabic) or type it.
  The Python backend compares your recitation with the ayah and shows **Memorized** or **Not memorized yet**,
  with missed/wrong words highlighted in red.
- **Progress saved** per browser in SQLite (read count, attempts, best accuracy, memorized status).

## Tech stack

| Layer    | Tech |
|----------|------|
| Backend  | Python 3.10+, Flask, SQLite |
| Frontend | HTML, CSS, vanilla JavaScript |
| Data     | [quran.com API v4](https://api-docs.quran.com/) (cached in SQLite after first fetch) |

Translations: Saheeh International (English), Maulana Azizul Haque al-Umari (Hindi), Fateh Muhammad Jalandhari (Urdu).

## Running locally

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py                    # http://localhost:5000 (FLASK_DEBUG=1 for debug mode)
```

Use **Google Chrome or Microsoft Edge** for microphone recitation (other browsers can use *Type instead*).
The microphone only works on `localhost` or over HTTPS.

## Tests

```bash
pytest
```

## Project layout

```
app.py            Flask app and JSON API
quran_api.py      quran.com API client with SQLite cache
recitation.py     Arabic normalisation + recitation comparison
db.py             SQLite schema / connection helpers
templates/        HTML
static/css, js/   Styles and frontend logic
tests/            pytest tests
```

## API

| Method | Path | Description |
|--------|------|-------------|
| GET  | `/api/surahs` | List of surahs |
| GET  | `/api/ayah/<surah>/<ayah>` | Ayah text, translations, word-by-word, audio, progress |
| POST | `/api/progress/<surah>/<ayah>/read` | Increase reading counter by one |
| POST | `/api/progress/<surah>/<ayah>/reset` | Reset progress for the ayah |
| GET  | `/api/progress` | All progress for the current user |
| POST | `/api/recite/<surah>/<ayah>` | `{"transcript": "..."}` → memorized verdict and per-word result |

Progress is keyed by an anonymous id stored in the browser (`X-User-Id` header).
