"""Deterministic human-readable presentation context generator for external analysis.

Transforms causal feed features and timestamps into natural Vietnamese labels,
correct units (USDT, BTC, %), and UTC+7 dates without lookahead leakage.
"""

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional


UTC_PLUS_7 = timezone(timedelta(hours=7))


def format_utc7_timestamp(ms: Optional[int]) -> str:
    """Formats epoch millisecond timestamp to dd/MM/yyyy HH:mm:ss (UTC+7)."""
    if ms is None or ms <= 0:
        return "N/A"
    dt = datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc).astimezone(UTC_PLUS_7)
    return dt.strftime("%d/%m/%Y %H:%M:%S (UTC+7)")


def format_ratio_to_percentage(ratio_val: Optional[float], decimals: int = 4) -> str:
    """Converts a unit=ratio float to a percentage string, e.g. 0.001768 -> +0.1768%."""
    if ratio_val is None:
        return "—"
    # Guard negative zero
    if abs(ratio_val) < 1e-9:
        return "0.0%"
    pct = ratio_val * 100.0
    sign = "+" if pct > 0 else ""
    # Avoid scientific notation
    formatted = f"{pct:.{decimals}f}".rstrip("0").rstrip(".")
    if not formatted or formatted == "-0":
        formatted = "0.0"
    return f"{sign}{formatted}%"


def format_usdt_amount(val: Optional[float], decimals: int = 2) -> str:
    """Formats price in USDT."""
    if val is None:
        return "—"
    return f"{val:,.{decimals}f} USDT"


def format_btc_volume(val: Optional[float], decimals: int = 4) -> str:
    """Formats volume in BTC."""
    if val is None:
        return "—"
    return f"{val:,.{decimals}f} BTC"


def build_readable_presentation_context(
    feed_dict: Dict[str, Any],
    purchase_price_p: Optional[float] = None,
) -> Dict[str, Any]:
    """Builds a deterministic, natural Vietnamese context dict from feed_dict.

    Does not modify raw feed provenance.
    """
    symbol = feed_dict.get("symbol", "BTCUSDT")
    timeframe = feed_dict.get("timeframe", "5m")
    t_ms = feed_dict.get("prediction_time_t_ms")
    p_val = purchase_price_p if purchase_price_p is not None else feed_dict.get("purchase_price_p", 0.0)
    horizon = feed_dict.get("horizon_minutes", 30)
    candles = feed_dict.get("candles", [])

    start_ms = candles[0]["open_time_ms"] if candles else None
    end_ms = candles[-1]["close_time_ms"] if candles else None

    # Map raw features
    features_list = feed_dict.get("features", [])
    feat_map = {f.get("feature_id"): f.get("value") for f in features_list if isinstance(f, dict)}

    formatted_features = []
    if "latest_close_vs_p_pct" in feat_map:
        val = feat_map["latest_close_vs_p_pct"]
        formatted_features.append({
            "name": "Chênh lệch giá đóng cửa gần nhất so với giá mua (P)",
            "value": format_ratio_to_percentage(val),
            "unit": "Tỷ lệ %",
            "raw_id": "latest_close_vs_p_pct",
        })
    if "range_high_6h" in feat_map:
        val = feat_map["range_high_6h"]
        formatted_features.append({
            "name": "Phạm vi giá cao nhất trong 6 giờ",
            "value": format_usdt_amount(val),
            "unit": "USDT",
            "raw_id": "range_high_6h",
        })
    if "range_low_6h" in feat_map:
        val = feat_map["range_low_6h"]
        formatted_features.append({
            "name": "Phạm vi giá thấp nhất trong 6 giờ",
            "value": format_usdt_amount(val),
            "unit": "USDT",
            "raw_id": "range_low_6h",
        })
    if "volatility_6h_pct" in feat_map:
        val = feat_map["volatility_6h_pct"]
        formatted_features.append({
            "name": "Biến động giá trong 6 giờ",
            "value": format_ratio_to_percentage(val),
            "unit": "Tỷ lệ %",
            "raw_id": "volatility_6h_pct",
        })
    if "total_volume_6h" in feat_map:
        val = feat_map["total_volume_6h"]
        formatted_features.append({
            "name": "Tổng khối lượng giao dịch trong 6 giờ",
            "value": format_btc_volume(val),
            "unit": "BTC",
            "raw_id": "total_volume_6h",
        })
    if "return_1h" in feat_map:
        val = feat_map["return_1h"]
        formatted_features.append({
            "name": "Biến động giá trong 1 giờ gần nhất",
            "value": format_ratio_to_percentage(val),
            "unit": "Tỷ lệ %",
            "raw_id": "return_1h",
        })
    if "last_candle_body_ratio" in feat_map:
        val = feat_map["last_candle_body_ratio"]
        formatted_features.append({
            "name": "Tỷ lệ thân nến cuối cùng",
            "value": format_ratio_to_percentage(val, decimals=1),
            "unit": "% tổng biên độ nến",
            "raw_id": "last_candle_body_ratio",
        })
    if "last_candle_upper_wick_ratio" in feat_map:
        val = feat_map["last_candle_upper_wick_ratio"]
        formatted_features.append({
            "name": "Tỷ lệ bóng trên nến cuối cùng",
            "value": format_ratio_to_percentage(val, decimals=1),
            "unit": "% tổng biên độ nến",
            "raw_id": "last_candle_upper_wick_ratio",
        })
    if "last_candle_lower_wick_ratio" in feat_map:
        val = feat_map["last_candle_lower_wick_ratio"]
        formatted_features.append({
            "name": "Tỷ lệ bóng dưới nến cuối cùng",
            "value": format_ratio_to_percentage(val, decimals=1),
            "unit": "% tổng biên độ nến",
            "raw_id": "last_candle_lower_wick_ratio",
        })

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "prediction_time_utc7": format_utc7_timestamp(t_ms),
        "purchase_price_formatted": format_usdt_amount(p_val),
        "horizon_minutes": horizon,
        "window_duration": "6 giờ",
        "window_start_utc7": format_utc7_timestamp(start_ms),
        "window_end_utc7": format_utc7_timestamp(end_ms),
        "candle_count": len(candles),
        "canonical_metrics": formatted_features,
    }
