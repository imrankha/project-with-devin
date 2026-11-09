import os
import re

from flask import Flask, jsonify, render_template, request

import quran_api
import recitation
from db import close_db, get_db, init_db

REQUIRED_READS = 25
_USER_ID = re.compile(r"^[A-Za-z0-9-]{8,64}$")


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    os.makedirs(app.instance_path, exist_ok=True)
    app.config.from_mapping(DATABASE=os.path.join(app.instance_path, "quran.db"))
    if test_config:
        app.config.update(test_config)

    init_db(app.config["DATABASE"])
    app.teardown_appcontext(close_db)

    def user_id() -> str:
        uid = request.headers.get("X-User-Id", "")
        return uid if _USER_ID.match(uid) else "anonymous"

    def valid_key(surah: int, ayah: int) -> str | None:
        surahs = {s["id"]: s for s in quran_api.get_surahs()}
        if surah not in surahs or not 1 <= ayah <= surahs[surah]["verses_count"]:
            return None
        return f"{surah}:{ayah}"

    def load_progress(verse_key: str) -> dict:
        row = get_db().execute(
            "SELECT read_count, memorized, best_accuracy, attempts FROM progress"
            " WHERE user_id = ? AND verse_key = ?",
            (user_id(), verse_key),
        ).fetchone()
        data = dict(row) if row else {"read_count": 0, "memorized": 0, "best_accuracy": 0, "attempts": 0}
        data["memorized"] = bool(data["memorized"])
        data["verse_key"] = verse_key
        data["required_reads"] = REQUIRED_READS
        data["can_recite"] = data["read_count"] >= REQUIRED_READS
        return data

    def ensure_row(verse_key: str) -> None:
        get_db().execute(
            "INSERT OR IGNORE INTO progress (user_id, verse_key) VALUES (?, ?)",
            (user_id(), verse_key),
        )

    @app.errorhandler(quran_api.QuranAPIError)
    def api_error(exc):
        return jsonify(error=str(exc)), 502

    @app.get("/")
    def index():
        return render_template("index.html", required_reads=REQUIRED_READS)

    @app.get("/api/surahs")
    def surahs():
        return jsonify(quran_api.get_surahs())

    @app.get("/api/ayah/<int:surah>/<int:ayah>")
    def ayah(surah, ayah):
        if not valid_key(surah, ayah):
            return jsonify(error="Invalid surah or ayah"), 404
        data = quran_api.get_ayah(surah, ayah)
        data["progress"] = load_progress(data["verse_key"])
        return jsonify(data)

    @app.post("/api/progress/<int:surah>/<int:ayah>/read")
    def add_read(surah, ayah):
        key = valid_key(surah, ayah)
        if not key:
            return jsonify(error="Invalid surah or ayah"), 404
        ensure_row(key)
        get_db().execute(
            "UPDATE progress SET read_count = read_count + 1, updated_at = CURRENT_TIMESTAMP"
            " WHERE user_id = ? AND verse_key = ?",
            (user_id(), key),
        )
        get_db().commit()
        return jsonify(load_progress(key))

    @app.post("/api/progress/<int:surah>/<int:ayah>/reset")
    def reset(surah, ayah):
        key = valid_key(surah, ayah)
        if not key:
            return jsonify(error="Invalid surah or ayah"), 404
        get_db().execute(
            "DELETE FROM progress WHERE user_id = ? AND verse_key = ?", (user_id(), key)
        )
        get_db().commit()
        return jsonify(load_progress(key))

    @app.get("/api/progress")
    def all_progress():
        rows = get_db().execute(
            "SELECT verse_key, read_count, memorized, best_accuracy FROM progress"
            " WHERE user_id = ? ORDER BY updated_at DESC",
            (user_id(),),
        ).fetchall()
        return jsonify([dict(r, memorized=bool(r["memorized"])) for r in rows])

    @app.post("/api/recite/<int:surah>/<int:ayah>")
    def recite(surah, ayah):
        key = valid_key(surah, ayah)
        if not key:
            return jsonify(error="Invalid surah or ayah"), 404
        progress = load_progress(key)
        if not progress["can_recite"]:
            return jsonify(
                error=f"Read this ayah at least {REQUIRED_READS} times before reciting.",
                progress=progress,
            ), 403
        transcript = ((request.get_json(silent=True) or {}).get("transcript") or "").strip()
        if not transcript:
            return jsonify(error="No recitation was captured. Please try again."), 400

        data = quran_api.get_ayah(surah, ayah)
        result = recitation.compare([w["imlaei"] for w in data["words"]], transcript)
        result["transcript"] = transcript

        ensure_row(key)
        get_db().execute(
            "UPDATE progress SET attempts = attempts + 1,"
            " best_accuracy = MAX(best_accuracy, ?),"
            " memorized = MAX(memorized, ?), updated_at = CURRENT_TIMESTAMP"
            " WHERE user_id = ? AND verse_key = ?",
            (result["accuracy"], int(result["memorized"]), user_id(), key),
        )
        get_db().commit()
        result["progress"] = load_progress(key)
        return jsonify(result)

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1", port=int(os.environ.get("PORT", "5000")))
