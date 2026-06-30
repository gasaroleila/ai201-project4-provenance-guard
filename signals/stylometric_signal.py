import re
import string
import statistics

MIDPOINT = 0.49625
MAX_DISTANCE = 0.23875

# 12-mark reference set from the spec (multi-char entries checked as substrings)
PUNCT_REFERENCE_SET = ['.', ',', '?', '!', ';', ':', '—','...', '""', '()', '/', '*']


def _tokenize_words(text: str) -> list:
    return re.findall(r"\b[a-zA-Z']+\b", text)


def _split_sentences(text: str) -> list:
    # Splits on .  !  ? followed by whitespace or end of string.
    # Assumption Q3: abbreviations (Dr., U.S.A.) may cause phantom short sentences.
    # Acceptable for prose paragraph input.
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return [s.strip() for s in sentences if s.strip()]


def _ttr(words: list) -> float:
    # Assumption Q2: raw TTR, not length-corrected. Longer texts will naturally score lower.
    if not words:
        return 0.0
    return len(set(w.lower() for w in words)) / len(words)


def _sentence_length_variance(sentences: list) -> float:
    # unique sentence word-lengths / total sentences.
    # Assumption Q4: single sentence returns 0.5 (neutral) since 1/1 = 1.0 is uninformative.
    if len(sentences) == 0:
        return 0.0
    if len(sentences) == 1:
        return 0.5
    lengths = [len(s.split()) for s in sentences]
    return len(set(lengths)) / len(lengths)


def _punctuation_richness(text: str) -> float:
    used = sum(1 for mark in PUNCT_REFERENCE_SET if mark in text)
    return used / len(PUNCT_REFERENCE_SET)


def _structural_entropy(text: str) -> float:
    # Gaps (in characters) between consecutive punctuation marks.
    # Higher std dev = more volatile spacing = more human.
    # Normalized via coefficient of variation (std / mean), clamped to [0, 1].
    positions = [i for i, c in enumerate(text) if c in string.punctuation]
    gaps = [positions[i + 1] - positions[i] for i in range(len(positions) - 1)]
    if len(gaps) < 2:
        return 0.5
    mean = statistics.mean(gaps)
    if mean == 0:
        return 0.0
    std = statistics.stdev(gaps)
    return min(1.0, std / mean)


def _punctuation_marker(text: str) -> float:
    return 0.5 * _punctuation_richness(text) + 0.5 * _structural_entropy(text)


def stylometric_signal(text: str) -> dict:
    words = _tokenize_words(text)
    sentences = _split_sentences(text)

    ttr = _ttr(words)
    slv = _sentence_length_variance(sentences)
    pm = _punctuation_marker(text)

    overall_variance_score = 0.4 * slv + 0.35 * pm + 0.25 * ttr

    attribution = "likely_human" if overall_variance_score >= MIDPOINT else "likely_ai"
    confidence = min(1.0, abs(overall_variance_score - MIDPOINT) / MAX_DISTANCE)

    return {
        "attribution": attribution,
        "confidence": round(confidence, 4),
        "heuristic_scores": {
            "ttr": round(ttr, 4),
            "sentence_length_variance": round(slv, 4),
            "punctuation_marker": round(pm, 4),
        },
        "overall_variance_score": round(overall_variance_score, 4),
    }
