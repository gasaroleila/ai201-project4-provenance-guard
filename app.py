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
    storage_uri="memory://"
)

MAX_WORDS = 500


def generate_transparency_label(attribution: str, confidence: float) -> str:
    if attribution == "likely_ai":
        if confidence >= 0.75:
            return (
                "Our system has identified strong, highly consistent patterns of AI generation in this text."
                "If this is an error, the creator can file an appeal via their dashboard."
            )
        if confidence >= 0.65:
            return (
                "Our system has detected moderate patterns commonly associated with AI generation tools."
                "If you believe this classification is incorrect, you may submit a quick review appeal."
            )
    if attribution == "likely_human":
        if confidence >= 0.75:
            return (
                "Our system is highly confident this content was written by a human creator. "
                "No significant patterns of AI generation were detected."
            )
        if confidence >= 0.65:
            return (
                "Our system is fairly confident this was written by a person. "
                "While some parts are uncertain, the overall style looks like natural human writing."
            )
    # covers: "uncertain" attribution and any attribution with confidence <0.65
    return (
        "Our system detected highly mixed signals in this text. "
        "There is not enough conclusive evidence to definitively classify it."
    )


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

    transparency_label = generate_transparency_label(combined["attribution"], combined["confidence"])

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

    return jsonify({"transparency_label": transparency_label, **result}), 200


@app.post("/appeal")
def appeal():
    data = request.get_json(silent=True)
    if not data or "content_id" not in data or "creator_reasoning" not in data:
        return jsonify({"error": "Request body must include 'content_id' and 'creator_reasoning' fields."}), 400

    content_id = data["content_id"]
    creator_reasoning = data["creator_reasoning"]

    with open(AUDIT_LOG_PATH, "r") as f:
        log = json.load(f)

    original = next((e for e in log if e.get("content_id") == content_id and e.get("status") == "classified"), None)
    if original is None:
        return jsonify({"error": f"No classified content found with content_id '{content_id}'."}), 404

    for entry in log:
        if entry.get("content_id") == content_id and entry.get("status") == "classified":
            entry["status"] = "under_review"

    appeal_entry = {
        "content_id": content_id,
        "creator_id": original["creator_id"],
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
        "original_attribution": original["attribution"],
        "original_confidence": original["confidence"],
        "creator_reasoning": creator_reasoning,
        "status": "under_review",
    }
    log.append(appeal_entry)

    with open(AUDIT_LOG_PATH, "w") as f:
        json.dump(log, f, indent=2)

    return jsonify({"message": "Your appeal has been received and is currently under review."}), 200


@app.get("/log")
def get_log():
    with open(AUDIT_LOG_PATH, "r") as f:
        log = json.load(f)
    return jsonify(log[-5:]), 200


if __name__ == "__main__":
    app.run(debug=True)
