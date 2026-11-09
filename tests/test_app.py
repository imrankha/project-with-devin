import pytest

import quran_api
from app import REQUIRED_READS, create_app

SURAHS = [{"id": 1, "name": "Al-Fatihah", "name_arabic": "الفاتحة", "translated_name": "The Opener",
           "verses_count": 7, "revelation_place": "makkah"}]
WORDS = ["الْحَمْدُ", "لِلَّهِ", "رَبِّ", "الْعَالَمِينَ"]
HEADERS = {"X-User-Id": "test-user-1234"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(quran_api, "get_surahs", lambda: SURAHS)
    monkeypatch.setattr(quran_api, "get_ayah", lambda s, a: {
        "verse_key": f"{s}:{a}", "surah": s, "ayah": a, "arabic": " ".join(WORDS),
        "translations": {"english": "e", "hindi": "h", "urdu": "u"},
        "words": [{"arabic": w, "imlaei": w, "meaning": {}} for w in WORDS],
        "audio_url": None,
    })
    app = create_app({"DATABASE": str(tmp_path / "test.db"), "TESTING": True})
    return app.test_client()


def test_index(client):
    assert client.get("/").status_code == 200


def test_invalid_ayah(client):
    assert client.get("/api/ayah/1/8").status_code == 404
    assert client.get("/api/ayah/115/1").status_code == 404


def test_counter_and_recite_flow(client):
    data = client.get("/api/ayah/1/2", headers=HEADERS).get_json()
    assert data["progress"]["read_count"] == 0

    resp = client.post("/api/recite/1/2", json={"transcript": "الحمد لله رب العالمين"}, headers=HEADERS)
    assert resp.status_code == 403

    for _ in range(REQUIRED_READS):
        progress = client.post("/api/progress/1/2/read", headers=HEADERS).get_json()
    assert progress["read_count"] == REQUIRED_READS
    assert progress["can_recite"] is True

    fail = client.post("/api/recite/1/2", json={"transcript": "الحمد"}, headers=HEADERS).get_json()
    assert fail["memorized"] is False
    assert fail["progress"]["memorized"] is False

    ok = client.post("/api/recite/1/2", json={"transcript": "الحمد لله رب العالمين"}, headers=HEADERS).get_json()
    assert ok["memorized"] is True
    assert ok["progress"]["memorized"] is True
    assert ok["progress"]["attempts"] == 2

    # Progress is per user.
    other = client.get("/api/ayah/1/2", headers={"X-User-Id": "other-user-5678"}).get_json()
    assert other["progress"]["read_count"] == 0

    reset = client.post("/api/progress/1/2/reset", headers=HEADERS).get_json()
    assert reset["read_count"] == 0 and reset["memorized"] is False


def test_empty_transcript(client):
    for _ in range(REQUIRED_READS):
        client.post("/api/progress/1/1/read", headers=HEADERS)
    assert client.post("/api/recite/1/1", json={"transcript": " "}, headers=HEADERS).status_code == 400
