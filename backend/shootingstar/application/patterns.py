"""Deterministic candle-pattern criteria diagnostics attached to analysis reports.

Operates only on causal candles; no forward returns or statistics.
"""

from typing import Any, Dict, List

from shootingstar.application.external_analysis.contracts import (
    PatternCriterion,
    PatternDiagnosticContract,
)
from shootingstar.domain.models import Candle


def evaluate_pattern_diagnostics(
    candles: List[Candle],
    target_index: int = -1,
    feed_hash: str = "ad_hoc_evaluation",
) -> List[PatternDiagnosticContract]:
    """Evaluates granular pattern criteria diagnostics at cutoff without any lookahead.

    STRICT INVARIANT: Operates strictly on causal historical candles available at target_index.
    No forward return calculation or future candle inspection.
    """
    if not candles:
        return []

    n = len(candles)
    idx = target_index if target_index >= 0 else (n + target_index)
    if idx < 0 or idx >= n:
        return []

    c = candles[idx]
    rng = c.high - c.low
    body = abs(c.close - c.open)
    upper_wick = c.high - max(c.open, c.close)
    lower_wick = min(c.open, c.close) - c.low

    candle_id = f"candle_{c.open_time_ms}"
    diagnostics: List[PatternDiagnosticContract] = []

    # -------------------------------------------------------------
    # 1. Hammer Diagnostic
    # -------------------------------------------------------------
    h_criteria: List[PatternCriterion] = []
    if rng <= 1e-8:
        h_small_body_pass = False
        h_small_body_reason = "Range is zero or negative."
    else:
        b_ratio = body / rng
        h_small_body_pass = b_ratio <= 0.35
        h_small_body_reason = f"Body ratio {b_ratio:.3f} <= 0.35 threshold." if h_small_body_pass else f"Body ratio {b_ratio:.3f} > 0.35."
    h_criteria.append(
        PatternCriterion(
            criterion_id="hammer_small_body",
            description="Small real body near top of range",
            source_id_or_locator="CandleCharts glossary - Steve Nison",
            rule_origin="SYSTEM_OPERATIONAL",
            formula_or_params="B / R <= 0.35",
            measured_value=round(body / rng, 4) if rng > 1e-8 else 0.0,
            expected_relation="<= 0.35",
            status="PASS" if h_small_body_pass else "FAIL",
            reason=h_small_body_reason,
        )
    )

    h_lower_wick_2x_pass = lower_wick >= (2.0 * body) and lower_wick > 0
    h_criteria.append(
        PatternCriterion(
            criterion_id="hammer_lower_wick_2x_body",
            description="Lower shadow at least twice the height of the real body",
            source_id_or_locator="CandleCharts glossary - Steve Nison",
            rule_origin="SOURCE_EXPLICIT",
            formula_or_params="D >= 2 * B",
            measured_value=round(lower_wick / (body if body > 0 else 1e-8), 4),
            expected_relation=">= 2.0 * body",
            status="PASS" if h_lower_wick_2x_pass else "FAIL",
            reason=f"Lower shadow {lower_wick:.2f} >= 2*body {2.0*body:.2f}." if h_lower_wick_2x_pass else f"Lower shadow {lower_wick:.2f} < 2*body {2.0*body:.2f}.",
        )
    )

    h_long_lower_pass = (lower_wick / rng >= 0.55) if rng > 1e-8 else False
    h_criteria.append(
        PatternCriterion(
            criterion_id="hammer_long_lower_wick",
            description="Long lower shadow occupying at least 55% of candle range",
            source_id_or_locator="ShootingStar operational specification",
            rule_origin="SYSTEM_OPERATIONAL",
            formula_or_params="D / R >= 0.55",
            measured_value=round(lower_wick / rng, 4) if rng > 1e-8 else 0.0,
            expected_relation=">= 0.55",
            status="PASS" if h_long_lower_pass else "FAIL",
            reason=f"Lower shadow ratio {(lower_wick / rng if rng > 0 else 0):.3f} >= 0.55." if h_long_lower_pass else "Lower shadow does not dominate candle range.",
        )
    )

    h_small_upper_pass = (upper_wick / rng <= 0.15) if rng > 1e-8 else False
    h_criteria.append(
        PatternCriterion(
            criterion_id="hammer_small_upper_wick",
            description="Upper shadow very small or non-existent (<= 15% range)",
            source_id_or_locator="ShootingStar operational specification",
            rule_origin="SYSTEM_OPERATIONAL",
            formula_or_params="U / R <= 0.15",
            measured_value=round(upper_wick / rng, 4) if rng > 1e-8 else 0.0,
            expected_relation="<= 0.15",
            status="PASS" if h_small_upper_pass else "FAIL",
            reason=f"Upper shadow ratio {(upper_wick / rng if rng > 0 else 0):.3f} <= 0.15." if h_small_upper_pass else "Upper shadow exceeds 15% of range.",
        )
    )

    # Trend context
    if idx >= 3:
        h_downtrend_pass = candles[idx - 1].close < candles[idx - 3].close
        h_trend_status = "PASS" if h_downtrend_pass else "FAIL"
        h_trend_reason = "Prior 3-bar window shows declining close prices." if h_downtrend_pass else "Prior 3-bar window does not show lower close."
        h_measured_trend = candles[idx - 1].close - candles[idx - 3].close
    else:
        h_trend_status = "UNKNOWN"
        h_trend_reason = "Insufficient history before candle to verify downtrend context (needs >=3 prior bars)."
        h_measured_trend = 0.0

    h_criteria.append(
        PatternCriterion(
            criterion_id="hammer_prior_downtrend",
            description="Preceding short-term downtrend before the pattern",
            source_id_or_locator="CandleCharts glossary - Steve Nison",
            rule_origin="SOURCE_EXPLICIT",
            formula_or_params="close[-1] < close[-3]",
            measured_value=round(h_measured_trend, 4),
            expected_relation="close[-1] < close[-3]",
            status=h_trend_status,
            reason=h_trend_reason,
        )
    )

    h_shape_pass = h_small_body_pass and h_lower_wick_2x_pass and h_long_lower_pass and h_small_upper_pass
    h_shape_status = "PASS" if h_shape_pass else "FAIL"
    h_context_status = h_trend_status

    if any(cr.status == "FAIL" for cr in h_criteria):
        h_overall = "KHÔNG_KHỚP"
    elif any(cr.status == "UNKNOWN" for cr in h_criteria):
        h_overall = "CHƯA_ĐỦ_TIÊU_CHÍ"
    else:
        h_overall = "KHỚP_THEO_RULE_VERSION"

    diagnostics.append(
        PatternDiagnosticContract(
            pattern_id="Hammer",
            candidate_id=f"candidate_hammer_{c.open_time_ms}",
            rule_version="v1",
            feed_hash=feed_hash,
            candle_ids=[candle_id],
            criteria=h_criteria,
            shape_status=h_shape_status,
            context_status=h_context_status,
            confirmation_status="CHỜ_XÁC_NHẬN",
            overall_match_status=h_overall,
            conflicts=["Ngược xu hướng tăng nếu bối cảnh trước đó không phải giảm."] if h_context_status == "FAIL" else [],
            limitations=["Khớp hình dạng không chứng minh xác suất tăng; cần nến xác nhận sau t."],
        )
    )

    # -------------------------------------------------------------
    # 2. Shooting Star Diagnostic
    # -------------------------------------------------------------
    ss_criteria: List[PatternCriterion] = []
    if rng <= 1e-8:
        ss_small_body_pass = False
        ss_small_body_reason = "Range is zero or negative."
    else:
        b_ratio = body / rng
        ss_small_body_pass = b_ratio <= 0.35
        ss_small_body_reason = f"Body ratio {b_ratio:.3f} <= 0.35 threshold." if ss_small_body_pass else f"Body ratio {b_ratio:.3f} > 0.35."
    ss_criteria.append(
        PatternCriterion(
            criterion_id="shooting_star_small_body",
            description="Small real body near bottom of range",
            source_id_or_locator="CandleCharts glossary - Steve Nison",
            rule_origin="SYSTEM_OPERATIONAL",
            formula_or_params="B / R <= 0.35",
            measured_value=round(body / rng, 4) if rng > 1e-8 else 0.0,
            expected_relation="<= 0.35",
            status="PASS" if ss_small_body_pass else "FAIL",
            reason=ss_small_body_reason,
        )
    )

    ss_upper_wick_2x_pass = upper_wick >= (2.0 * body) and upper_wick > 0
    ss_criteria.append(
        PatternCriterion(
            criterion_id="shooting_star_upper_wick_2x_body",
            description="Upper shadow at least twice the height of the real body",
            source_id_or_locator="ShootingStar operational specification",
            rule_origin="SYSTEM_OPERATIONAL",
            formula_or_params="U >= 2 * B",
            measured_value=round(upper_wick / (body if body > 0 else 1e-8), 4),
            expected_relation=">= 2.0 * body",
            status="PASS" if ss_upper_wick_2x_pass else "FAIL",
            reason=f"Upper shadow {upper_wick:.2f} >= 2*body {2.0*body:.2f}." if ss_upper_wick_2x_pass else f"Upper shadow {upper_wick:.2f} < 2*body {2.0*body:.2f}.",
        )
    )

    ss_long_upper_pass = (upper_wick / rng >= 0.55) if rng > 1e-8 else False
    ss_criteria.append(
        PatternCriterion(
            criterion_id="shooting_star_long_upper_wick",
            description="Long upper shadow occupying at least 55% of candle range",
            source_id_or_locator="ShootingStar operational specification",
            rule_origin="SYSTEM_OPERATIONAL",
            formula_or_params="U / R >= 0.55",
            measured_value=round(upper_wick / rng, 4) if rng > 1e-8 else 0.0,
            expected_relation=">= 0.55",
            status="PASS" if ss_long_upper_pass else "FAIL",
            reason=f"Upper shadow ratio {(upper_wick / rng if rng > 0 else 0):.3f} >= 0.55." if ss_long_upper_pass else "Upper shadow does not dominate range.",
        )
    )

    ss_small_lower_pass = (lower_wick / rng <= 0.15) if rng > 1e-8 else False
    ss_criteria.append(
        PatternCriterion(
            criterion_id="shooting_star_small_lower_wick",
            description="Lower shadow very small or non-existent (<= 15% range)",
            source_id_or_locator="ShootingStar operational specification",
            rule_origin="SYSTEM_OPERATIONAL",
            formula_or_params="D / R <= 0.15",
            measured_value=round(lower_wick / rng, 4) if rng > 1e-8 else 0.0,
            expected_relation="<= 0.15",
            status="PASS" if ss_small_lower_pass else "FAIL",
            reason=f"Lower shadow ratio {(lower_wick / rng if rng > 0 else 0):.3f} <= 0.15." if ss_small_lower_pass else "Lower shadow exceeds 15% of range.",
        )
    )

    # Trend context
    if idx >= 3:
        ss_uptrend_pass = candles[idx - 1].close > candles[idx - 3].close
        ss_trend_status = "PASS" if ss_uptrend_pass else "FAIL"
        ss_trend_reason = "Prior 3-bar window shows rising close prices." if ss_uptrend_pass else "Prior 3-bar window does not show higher close."
        ss_measured_trend = candles[idx - 1].close - candles[idx - 3].close
    else:
        ss_trend_status = "UNKNOWN"
        ss_trend_reason = "Insufficient history before candle to verify uptrend context (needs >=3 prior bars)."
        ss_measured_trend = 0.0

    ss_criteria.append(
        PatternCriterion(
            criterion_id="shooting_star_prior_uptrend",
            description="Preceding short-term uptrend before the pattern",
            source_id_or_locator="CandleCharts glossary - Steve Nison",
            rule_origin="SOURCE_EXPLICIT",
            formula_or_params="close[-1] > close[-3]",
            measured_value=round(ss_measured_trend, 4),
            expected_relation="close[-1] > close[-3]",
            status=ss_trend_status,
            reason=ss_trend_reason,
        )
    )

    ss_shape_pass = ss_small_body_pass and ss_upper_wick_2x_pass and ss_long_upper_pass and ss_small_lower_pass
    ss_shape_status = "PASS" if ss_shape_pass else "FAIL"
    ss_context_status = ss_trend_status

    if any(cr.status == "FAIL" for cr in ss_criteria):
        ss_overall = "KHÔNG_KHỚP"
    elif any(cr.status == "UNKNOWN" for cr in ss_criteria):
        ss_overall = "CHƯA_ĐỦ_TIÊU_CHÍ"
    else:
        ss_overall = "KHỚP_THEO_RULE_VERSION"

    diagnostics.append(
        PatternDiagnosticContract(
            pattern_id="Shooting_Star",
            candidate_id=f"candidate_shooting_star_{c.open_time_ms}",
            rule_version="v1",
            feed_hash=feed_hash,
            candle_ids=[candle_id],
            criteria=ss_criteria,
            shape_status=ss_shape_status,
            context_status=ss_context_status,
            confirmation_status="CHỜ_XÁC_NHẬN",
            overall_match_status=ss_overall,
            conflicts=["Ngược xu hướng giảm nếu bối cảnh trước đó không phải tăng."] if ss_context_status == "FAIL" else [],
            limitations=["Khớp hình dạng không chứng minh xác suất giảm; cần nến xác nhận sau t."],
        )
    )

    # -------------------------------------------------------------
    # 3. Bullish Engulfing Diagnostic
    # -------------------------------------------------------------
    if idx >= 1:
        c_prev = candles[idx - 1]
        b_prev = abs(c_prev.close - c_prev.open)
        bull_c: List[PatternCriterion] = []

        c1_bear = c_prev.close < c_prev.open
        bull_c.append(
            PatternCriterion(
                criterion_id="bullish_engulfing_first_bearish",
                description="First candle of pair must be bearish (close < open)",
                source_id_or_locator="CandleCharts glossary - Steve Nison",
                rule_origin="SOURCE_EXPLICIT",
                formula_or_params="C1 < O1",
                measured_value=round(c_prev.close - c_prev.open, 4),
                expected_relation="< 0",
                status="PASS" if c1_bear else "FAIL",
                reason="First candle is red/bearish." if c1_bear else "First candle is not bearish.",
            )
        )

        c2_bull = c.close > c.open
        bull_c.append(
            PatternCriterion(
                criterion_id="bullish_engulfing_second_bullish",
                description="Second candle of pair must be bullish (close > open)",
                source_id_or_locator="CandleCharts glossary - Steve Nison",
                rule_origin="SOURCE_EXPLICIT",
                formula_or_params="C2 > O2",
                measured_value=round(c.close - c.open, 4),
                expected_relation="> 0",
                status="PASS" if c2_bull else "FAIL",
                reason="Second candle is green/bullish." if c2_bull else "Second candle is not bullish.",
            )
        )

        engulfs = (c.open <= c_prev.close) and (c.close >= c_prev.open)
        bull_c.append(
            PatternCriterion(
                criterion_id="bullish_engulfing_body_engulfs",
                description="Second real body completely engulfs prior real body",
                source_id_or_locator="CandleCharts glossary - Steve Nison",
                rule_origin="SOURCE_EXPLICIT",
                formula_or_params="O2 <= C1 and C2 >= O1",
                measured_value=round(body - b_prev, 4),
                expected_relation="O2 <= C1 and C2 >= O1",
                status="PASS" if engulfs else "FAIL",
                reason="Second real body covers entire first real body." if engulfs else "Second body does not fully cover first body.",
            )
        )

        larger_body = body > b_prev
        bull_c.append(
            PatternCriterion(
                criterion_id="bullish_engulfing_larger_body",
                description="Second real body is strictly larger than first real body",
                source_id_or_locator="CandleCharts glossary - Steve Nison",
                rule_origin="SOURCE_EXPLICIT",
                formula_or_params="B2 > B1",
                measured_value=round(body - b_prev, 4),
                expected_relation="B2 > B1",
                status="PASS" if larger_body else "FAIL",
                reason="Second body is larger than first body." if larger_body else "Second body is not larger than first body.",
            )
        )

        # Preceding trend before pair (ends before c_prev, i.e. idx-2 vs idx-4)
        if idx >= 4:
            bull_trend_pass = candles[idx - 2].close < candles[idx - 4].close
            bull_trend_status = "PASS" if bull_trend_pass else "FAIL"
            bull_trend_reason = "Prior downtrend before engulfing pair verified." if bull_trend_pass else "No prior downtrend detected before the pair."
            bull_measured_trend = candles[idx - 2].close - candles[idx - 4].close
        else:
            bull_trend_status = "UNKNOWN"
            bull_trend_reason = "Insufficient history before pair to verify preceding downtrend."
            bull_measured_trend = 0.0

        bull_c.append(
            PatternCriterion(
                criterion_id="bullish_engulfing_prior_downtrend",
                description="Preceding downtrend strictly ending before first candle of pair",
                source_id_or_locator="CandleCharts glossary - Steve Nison",
                rule_origin="SOURCE_EXPLICIT",
                formula_or_params="close[-2] < close[-4]",
                measured_value=round(bull_measured_trend, 4),
                expected_relation="close[-2] < close[-4]",
                status=bull_trend_status,
                reason=bull_trend_reason,
            )
        )

        b_shape_pass = c1_bear and c2_bull and engulfs and larger_body
        b_shape_status = "PASS" if b_shape_pass else "FAIL"
        b_context_status = bull_trend_status

        if any(cr.status == "FAIL" for cr in bull_c):
            b_overall = "KHÔNG_KHỚP"
        elif any(cr.status == "UNKNOWN" for cr in bull_c):
            b_overall = "CHƯA_ĐỦ_TIÊU_CHÍ"
        else:
            b_overall = "KHỚP_THEO_RULE_VERSION"

        diagnostics.append(
            PatternDiagnosticContract(
                pattern_id="Bullish_Engulfing",
                candidate_id=f"candidate_bull_engulf_{c.open_time_ms}",
                rule_version="v1",
                feed_hash=feed_hash,
                candle_ids=[f"candle_{c_prev.open_time_ms}", candle_id],
                criteria=bull_c,
                shape_status=b_shape_status,
                context_status=b_context_status,
                confirmation_status="CHỜ_XÁC_NHẬN",
                overall_match_status=b_overall,
                conflicts=["Sai xu hướng trước cặp nến."] if b_context_status == "FAIL" else [],
                limitations=["Cần bao phủ thân nến (không bắt buộc bóng); hiệu quả phụ thuộc bối cảnh."],
            )
        )

    # -------------------------------------------------------------
    # 4. Bearish Engulfing Diagnostic
    # -------------------------------------------------------------
    if idx >= 1:
        c_prev = candles[idx - 1]
        b_prev = abs(c_prev.close - c_prev.open)
        bear_c: List[PatternCriterion] = []

        c1_bull = c_prev.close > c_prev.open
        bear_c.append(
            PatternCriterion(
                criterion_id="bearish_engulfing_first_bullish",
                description="First candle of pair must be bullish (close > open)",
                source_id_or_locator="CandleCharts glossary - Steve Nison",
                rule_origin="SOURCE_EXPLICIT",
                formula_or_params="C1 > O1",
                measured_value=round(c_prev.close - c_prev.open, 4),
                expected_relation="> 0",
                status="PASS" if c1_bull else "FAIL",
                reason="First candle is green/bullish." if c1_bull else "First candle is not bullish.",
            )
        )

        c2_bear = c.close < c.open
        bear_c.append(
            PatternCriterion(
                criterion_id="bearish_engulfing_second_bearish",
                description="Second candle of pair must be bearish (close < open)",
                source_id_or_locator="CandleCharts glossary - Steve Nison",
                rule_origin="SOURCE_EXPLICIT",
                formula_or_params="C2 < O2",
                measured_value=round(c.close - c.open, 4),
                expected_relation="< 0",
                status="PASS" if c2_bear else "FAIL",
                reason="Second candle is red/bearish." if c2_bear else "Second candle is not bearish.",
            )
        )

        engulfs_bear = (c.open >= c_prev.close) and (c.close <= c_prev.open)
        bear_c.append(
            PatternCriterion(
                criterion_id="bearish_engulfing_body_engulfs",
                description="Second real body completely engulfs prior real body",
                source_id_or_locator="CandleCharts glossary - Steve Nison",
                rule_origin="SOURCE_EXPLICIT",
                formula_or_params="O2 >= C1 and C2 <= O1",
                measured_value=round(body - b_prev, 4),
                expected_relation="O2 >= C1 and C2 <= O1",
                status="PASS" if engulfs_bear else "FAIL",
                reason="Second real body covers entire first real body." if engulfs_bear else "Second body does not fully cover first body.",
            )
        )

        larger_body_bear = body > b_prev
        bear_c.append(
            PatternCriterion(
                criterion_id="bearish_engulfing_larger_body",
                description="Second real body is strictly larger than first real body",
                source_id_or_locator="CandleCharts glossary - Steve Nison",
                rule_origin="SOURCE_EXPLICIT",
                formula_or_params="B2 > B1",
                measured_value=round(body - b_prev, 4),
                expected_relation="B2 > B1",
                status="PASS" if larger_body_bear else "FAIL",
                reason="Second body is larger than first body." if larger_body_bear else "Second body is not larger than first body.",
            )
        )

        # Preceding uptrend before pair (ends before c_prev, i.e. idx-2 vs idx-4)
        if idx >= 4:
            bear_trend_pass = candles[idx - 2].close > candles[idx - 4].close
            bear_trend_status = "PASS" if bear_trend_pass else "FAIL"
            bear_trend_reason = "Prior uptrend before engulfing pair verified." if bear_trend_pass else "No prior uptrend detected before the pair."
            bear_measured_trend = candles[idx - 2].close - candles[idx - 4].close
        else:
            bear_trend_status = "UNKNOWN"
            bear_trend_reason = "Insufficient history before pair to verify preceding uptrend."
            bear_measured_trend = 0.0

        bear_c.append(
            PatternCriterion(
                criterion_id="bearish_engulfing_prior_uptrend",
                description="Preceding uptrend strictly ending before first candle of pair",
                source_id_or_locator="CandleCharts glossary - Steve Nison",
                rule_origin="SOURCE_EXPLICIT",
                formula_or_params="close[-2] > close[-4]",
                measured_value=round(bear_measured_trend, 4),
                expected_relation="close[-2] > close[-4]",
                status=bear_trend_status,
                reason=bear_trend_reason,
            )
        )

        be_shape_pass = c1_bull and c2_bear and engulfs_bear and larger_body_bear
        be_shape_status = "PASS" if be_shape_pass else "FAIL"
        be_context_status = bear_trend_status

        if any(cr.status == "FAIL" for cr in bear_c):
            be_overall = "KHÔNG_KHỚP"
        elif any(cr.status == "UNKNOWN" for cr in bear_c):
            be_overall = "CHƯA_ĐỦ_TIÊU_CHÍ"
        else:
            be_overall = "KHỚP_THEO_RULE_VERSION"

        diagnostics.append(
            PatternDiagnosticContract(
                pattern_id="Bearish_Engulfing",
                candidate_id=f"candidate_bear_engulf_{c.open_time_ms}",
                rule_version="v1",
                feed_hash=feed_hash,
                candle_ids=[f"candle_{c_prev.open_time_ms}", candle_id],
                criteria=bear_c,
                shape_status=be_shape_status,
                context_status=be_context_status,
                confirmation_status="CHỜ_XÁC_NHẬN",
                overall_match_status=be_overall,
                conflicts=["Sai xu hướng trước cặp nến."] if be_context_status == "FAIL" else [],
                limitations=["Cần bao phủ thân nến (không bắt buộc bóng); hiệu quả phụ thuộc bối cảnh."],
            )
        )

    return diagnostics


def pattern_diagnostics_to_dict(diag: PatternDiagnosticContract) -> Dict[str, Any]:
    """Serializes PatternDiagnosticContract into JSON-compatible dict."""
    return {
        "pattern_id": diag.pattern_id,
        "candidate_id": diag.candidate_id,
        "rule_version": diag.rule_version,
        "feed_hash": diag.feed_hash,
        "candle_ids": diag.candle_ids,
        "shape_status": diag.shape_status,
        "context_status": diag.context_status,
        "confirmation_status": diag.confirmation_status,
        "overall_match_status": diag.overall_match_status,
        "conflicts": diag.conflicts,
        "limitations": diag.limitations,
        "predictive_evidence_status": diag.predictive_evidence_status,
        "criteria": [
            {
                "criterion_id": cr.criterion_id,
                "description": cr.description,
                "source_id_or_locator": cr.source_id_or_locator,
                "rule_origin": cr.rule_origin,
                "formula_or_params": cr.formula_or_params,
                "measured_value": cr.measured_value,
                "expected_relation": cr.expected_relation,
                "status": cr.status,
                "reason": cr.reason,
            }
            for cr in diag.criteria
        ],
    }
