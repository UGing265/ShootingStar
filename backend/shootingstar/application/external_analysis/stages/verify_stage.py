"""Check cited numbers, excluding timeframe units, indicator periods and identifier tokens."""

import math
import re

_NUMBER = re.compile(r"(?<![\w.])[-+]?(?:\d+(?:\.\d+)?|\.\d+)(?![\w.])")
_PERIOD_SUFFIX = re.compile(r"\s*(?:giờ|ngày|phút|tuần|nến|kỳ|phiên|h|d|m)(?!\w)", re.IGNORECASE)
_INDICATOR_PREFIX = re.compile(r"(?:RSI|EMA|MACD|ATR|SMA)\)?(?:\s*\d+\s*(?:,|và|/))*\s*$", re.IGNORECASE)
_DIRECTION = re.compile(r"\b(?:giảm|âm|tăng|dương)\b", re.IGNORECASE)


def verify(answer, digest, purchase_price=None, horizon_minutes=None):
    features = {item["feature_id"]: item["value"] for item in digest["features"]}
    units = {item["feature_id"]: item.get("unit") for item in digest["features"]}
    issues = []
    for index, reason in enumerate(answer["reasons"]):
        ids = reason["feature_ids"]
        for feature_id in ids:
            if feature_id not in features:
                issues.append({"reason_index": index, "type": "unknown_feature_id", "value": feature_id})
        values = [(features[k], units[k]) for k in ids if k in features and features[k] is not None]
        cites_rsi = any("rsi" in k.lower() for k in ids if k in features)
        text = reason["text"]
        for match in _NUMBER.finditer(text):
            token = match.group()
            if (_PERIOD_SUFFIX.match(text, match.end()) or
                    (token.isdigit() and _INDICATOR_PREFIX.search(text[:match.start()]))):
                continue
            number = float(token)
            if number == 0 or (cites_rsi and number in (30, 50, 70)):
                continue
            decimals = len(token.split(".", 1)[1]) if "." in token else 0
            tolerance = 10 ** -decimals + 1e-9
            directions = list(_DIRECTION.finditer(text[:match.start()]))
            negative_direction = bool(directions and directions[-1].group().lower() in ("giảm", "âm"))
            percent = text[match.end():].lstrip().startswith("%")
            if not percent and (number == horizon_minutes or (
                    purchase_price is not None and math.isclose(number, purchase_price, rel_tol=0, abs_tol=tolerance))):
                continue
            if not any(
                math.isclose(number, value, rel_tol=0, abs_tol=tolerance)
                or (not token.startswith(("+", "-")) and negative_direction and value < 0
                    and math.isclose(number, -value, rel_tol=0, abs_tol=tolerance))
                for raw, unit in values
                for value in (raw * 100 if percent and unit == "ratio" else raw,)
            ):
                issues.append({"reason_index": index, "type": "unmatched_number", "value": token})
    return {"valid": not issues, "issues": issues}
