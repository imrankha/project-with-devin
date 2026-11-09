"""Fetch Quran data from the public quran.com API and cache it in SQLite."""

import json
import re

import requests

from db import get_db

API_BASE = "https://api.quran.com/api/v4"
VERSE_AUDIO_BASE = "https://verses.quran.com/"
WORD_AUDIO_BASE = "https://audio.qurancdn.com/"

# quran.com translation resource ids.
TRANSLATIONS = {
    "english": 20,  # Saheeh International
    "hindi": 122,  # Maulana Azizul Haque al-Umari
    "urdu": 234,  # Fateh Muhammad Jalandhari
}
WORD_LANGUAGES = {"english": "en", "hindi": "hi", "urdu": "ur"}
RECITER_ID = 7  # Mishari Rashid al-Afasy

_FOOTNOTE = re.compile(r"<sup[^>]*>.*?</sup>", re.DOTALL)
_TAGS = re.compile(r"<[^>]+>")


class QuranAPIError(Exception):
    pass


def _clean(text: str) -> str:
    return _TAGS.sub("", _FOOTNOTE.sub("", text or "")).strip()


def _fetch_json(path: str, params: dict | None = None) -> dict:
    cache_key = path + "?" + json.dumps(params or {}, sort_keys=True)
    db = get_db()
    row = db.execute("SELECT value FROM api_cache WHERE key = ?", (cache_key,)).fetchone()
    if row:
        return json.loads(row["value"])
    try:
        resp = requests.get(API_BASE + path, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError) as exc:
        raise QuranAPIError(f"Could not load data from quran.com: {exc}") from exc
    db.execute(
        "INSERT OR REPLACE INTO api_cache (key, value) VALUES (?, ?)",
        (cache_key, json.dumps(data)),
    )
    db.commit()
    return data


def get_surahs() -> list[dict]:
    data = _fetch_json("/chapters", {"language": "en"})
    return [
        {
            "id": c["id"],
            "name": c["name_simple"],
            "name_arabic": c["name_arabic"],
            "translated_name": c["translated_name"]["name"],
            "verses_count": c["verses_count"],
            "revelation_place": c["revelation_place"],
        }
        for c in data["chapters"]
    ]


def get_ayah(surah: int, ayah: int) -> dict:
    verse_key = f"{surah}:{ayah}"
    translation_ids = ",".join(str(i) for i in TRANSLATIONS.values())

    by_language = {}
    for lang, code in WORD_LANGUAGES.items():
        by_language[lang] = _fetch_json(
            f"/verses/by_key/{verse_key}",
            {
                "language": code,
                "words": "true",
                "fields": "text_uthmani,text_imlaei",
                "word_fields": "text_uthmani,text_imlaei",
                "translations": translation_ids,
            },
        )["verse"]

    base = by_language["english"]
    translations_by_id = {t["resource_id"]: _clean(t["text"]) for t in base.get("translations", [])}

    words = []
    word_lists = {lang: [w for w in v["words"] if w["char_type_name"] == "word"]
                  for lang, v in by_language.items()}
    for idx, w in enumerate(word_lists["english"]):
        words.append(
            {
                "position": w["position"],
                "arabic": w["text_uthmani"],
                "imlaei": w.get("text_imlaei") or w["text_uthmani"],
                "transliteration": (w.get("transliteration") or {}).get("text"),
                "audio_url": WORD_AUDIO_BASE + w["audio_url"] if w.get("audio_url") else None,
                "meaning": {
                    lang: (word_lists[lang][idx].get("translation") or {}).get("text")
                    if idx < len(word_lists[lang]) else None
                    for lang in WORD_LANGUAGES
                },
            }
        )

    audio = _fetch_json(f"/recitations/{RECITER_ID}/by_ayah/{verse_key}")
    audio_files = audio.get("audio_files") or []
    audio_url = None
    if audio_files:
        url = audio_files[0]["url"]
        audio_url = url if url.startswith("http") else VERSE_AUDIO_BASE + url

    return {
        "verse_key": verse_key,
        "surah": surah,
        "ayah": ayah,
        "arabic": base["text_uthmani"],
        "arabic_simple": base.get("text_imlaei"),
        "translations": {lang: translations_by_id.get(rid, "") for lang, rid in TRANSLATIONS.items()},
        "words": words,
        "audio_url": audio_url,
    }
