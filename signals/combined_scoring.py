def combined_scoring(signal1: dict, signal2: dict) -> dict:
    """
    Combines LLM signal and stylometric signal into a final attribution and confidence score.

    Cases:
      1. Agree on attribution → weighted average (0.6 LLM + 0.4 heuristic)
      2. Disagree, |diff| > 0.35 → take the higher-confidence signal
      3. Disagree, |diff| <= 0.35 → uncertain, confidence = 0.5
    """
    llm_attribution = signal1["attribution"]
    llm_score = signal1["confidence"]
    heuristic_attribution = signal2["attribution"]
    heuristic_score = signal2["confidence"]

    if llm_attribution == heuristic_attribution:
        # Case 1: signals agree
        confidence = round(0.6 * llm_score + 0.4 * heuristic_score, 4)
        attribution = llm_attribution
        case = "agree"
    else:
        score_diff = abs(llm_score - heuristic_score)
        if score_diff > 0.35:
            # Case 2: far apart — trust the more confident signal
            if llm_score >= heuristic_score:
                confidence = round(llm_score, 4)
                attribution = llm_attribution
            else:
                confidence = round(heuristic_score, 4)
                attribution = heuristic_attribution
            case = "disagree_far"
        else:
            # Case 3: close scores (diff <= 0.35) — genuinely uncertain
            confidence = 0.5
            attribution = "uncertain"
            case = "disagree_close"

    return {
        "attribution": attribution,
        "confidence": confidence,
        "case": case,
    }
