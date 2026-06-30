import json
import uuid
import os
from datetime import datetime, timezone

from flask import Flask, request, jsonify
from flask_limiter import Limiter
from dotenv import load_dotenv

from signals.llm_signal import llm_signal
from signals.stylometric_signal import stylometric_signal
from signals.combined_scoring import combined_scoring

load_dotenv()

app = Flask(__name__)

AUDIT_LOG_PATH = os.path.join(os.path.dirname(__file__), "logs", "audit_log.json")


def get_creator_id():
    data = request.get_json(silent=True)
    if data and "creator_id" in data:
        return data["creator_id"]
    return "anonymous"


limiter = Limiter(
    get_creator_id,
    app=app,
    default_limits=[],
)

MAX_WORDS = 500


def append_to_audit_log(entry: dict):
    with open(AUDIT_LOG_PATH, "r") as f:
        log = json.load(f)
    log.append(entry)
    with open(AUDIT_LOG_PATH, "w") as f:
        json.dump(log, f, indent=2)


@app.post("/submit")
@limiter.limit("5 per hour")
def submit():
    data = request.get_json(silent=True)
    if not data or "text" not in data or "creator_id" not in data:
        return jsonify({"error": "Request body must include 'text' and 'creator_id' fields."}), 400

    text = data["text"]
    creator_id = data["creator_id"]
    word_count = len(text.split())
    if word_count > MAX_WORDS:
        return jsonify({"error": f"Text exceeds {MAX_WORDS}-word limit ({word_count} words)."}), 400

    signal1 = llm_signal(text)
    signal2 = stylometric_signal(text)
    combined = combined_scoring(signal1, signal2)

    print(f"\n[DEBUG] Signal 1 (LLM)         → attribution: {signal1['attribution']}, confidence: {signal1['confidence']}")
    print(f"[DEBUG] Signal 2 (Stylometric)  → attribution: {signal2['attribution']}, confidence: {signal2['confidence']}")
    print(f"[DEBUG] Combined ({combined['case']}) → attribution: {combined['attribution']}, confidence: {combined['confidence']}\n")

    # TODO (M5): generate transparency_label

    result = {
        "content_id": str(uuid.uuid4()),
        "creator_id": creator_id,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
        "attribution": combined["attribution"],
        "confidence": combined["confidence"],
        "llm_score": signal1["confidence"],
        "heuristic_score": signal2["confidence"],
        "status": "classified",
    }

    append_to_audit_log(result)

    return jsonify(result), 200


@app.get("/log")
def get_log():
    with open(AUDIT_LOG_PATH, "r") as f:
        log = json.load(f)
    return jsonify(log[-5:]), 200


if __name__ == "__main__":
    app.run(debug=True)
