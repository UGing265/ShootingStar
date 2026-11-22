"""Validate structured model output without fabricating a fallback."""

from shootingstar.adapters.model_api.gemini_transport import GeminiAPIError


def analyze(adapter, digest, horizon_minutes, purchase_price):
    answer, usage = adapter.forecast(digest, horizon_minutes, purchase_price)
    if not isinstance(answer, dict) or answer.get("direction") not in ("UP", "DOWN") or answer.get("confidence") not in ("LOW", "MEDIUM", "HIGH"):
        raise GeminiAPIError("Invalid forecast direction or confidence")
    reasons, risks = answer.get("reasons"), answer.get("risks")
    if not isinstance(reasons, list) or not reasons or not isinstance(risks, list) or any(not isinstance(x, str) for x in risks):
        raise GeminiAPIError("Invalid forecast reasons or risks")
    for reason in reasons:
        if (not isinstance(reason, dict) or not isinstance(reason.get("text"), str) or not reason["text"].strip()
                or not isinstance(reason.get("feature_ids"), list) or not reason["feature_ids"]
                or any(not isinstance(x, str) or not x for x in reason["feature_ids"])):
            raise GeminiAPIError("Invalid forecast reason")
    return answer, usage
