"""Count directional evidence, not confidence or probability."""

from shootingstar.application.forecast.technical_digest import TechnicalDigest


def agreement_score(digest: TechnicalDigest) -> dict[str, int]:
    """Each EMA slope, RSI, MACD histogram and 6h return gets one vote.

    Slopes, histogram and return above/below zero vote UP/DOWN; RSI above/below
    50 votes UP/DOWN. Equality and missing values do not vote. Total counts votes.
    """
    up = down = 0
    for feature in digest["features"]:
        name, value = feature["name"], feature["value"]
        if value is None:
            continue
        if name in ("ema20_slope", "ema50_slope", "macd_hist", "return_6h"):
            neutral = 0
        elif name == "rsi14":
            neutral = 50
        else:
            continue
        up += value > neutral
        down += value < neutral
    return {"up": up, "down": down, "total": up + down}
