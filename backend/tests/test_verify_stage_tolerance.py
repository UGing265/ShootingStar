"""Verifier accepts equivalent numeric descriptions but flags unsupported claims."""

from shootingstar.application.external_analysis.stages.verify_stage import verify


def _result(value, text, feature_id="1h_rsi14", ids=None):
    digest = {"features": [{"feature_id": feature_id, "value": value}]}
    answer = {"reasons": [{"feature_ids": ids or [feature_id], "text": text}]}
    return verify(answer, digest)


def test_truncation_and_rounding_at_written_precision():
    assert _result(-0.1595586, "Giá trị -0.159")['valid']
    assert _result(-0.1595586, "Giá trị -0.160")['valid']
    assert not _result(-0.1595586, "Giá trị -0.162")['valid']


def test_direction_word_can_replace_negative_sign():
    assert _result(-0.60730865, "mức giảm 0.6073%")['valid']
    assert not _result(-0.60730865, "mức giảm 0.6100%")['valid']
    assert not _result(-0.60730865, "mức tăng 0.6073%")['valid']
    assert not _result(-0.60730865, "giá trị +0.6073%")['valid']
    assert not _result(-0.60730865, "giá trị 0.6073%")['valid']


def test_reference_levels_and_unknown_or_fabricated_values():
    assert _result(45.1234, "RSI 14 dưới 50, trên 30 và dưới 70; so với 0")['valid']
    assert _result(45.1234, "EMA 20 và EMA 50")['valid']
    assert not _result(45.1234, "RSI 14 ở 72.5")['valid']
    assert not _result(45.1234, "ở 50", "1h_ema20_slope")['valid']
    result = _result(45.1234, "dưới 50", ids=["missing"])
    assert any(issue['type'] == 'unknown_feature_id' for issue in result['issues'])


def test_indicator_period_lists_and_candle_periods():
    assert _result(-0.0326, "(EMA) 20 và 50 có độ dốc -0.0326%", "1h_ema20_slope")['valid']
    assert _result(1.74129309, "trung bình 20 kỳ (1.74129309)", "1h_volume_ratio20")['valid']
    assert _result(1.74129309, "trung bình 20 phiên (1.74129309)", "1h_volume_ratio20")['valid']
    assert not _result(-0.0326, "EMA 20 và 50 có giá trị 72.5", "1h_ema20_slope")['valid']
    assert not _result(-0.0326, "Giá 20 và 50", "1h_ema20_slope")['valid']


def test_ratio_features_can_be_expressed_as_percent_only_with_percent_unit():
    digest = {"features": [{"feature_id": "range", "unit": "ratio", "value": 0.39039115}]}
    def result(text):
        return verify({"reasons": [{"feature_ids": ["range"], "text": text}]}, digest)
    assert result("Giá trong phạm vi 39.04%")['valid']
    assert not result("Giá trong phạm vi 39.04")['valid']
    assert not result("Giá trong phạm vi 0.39%")['valid']
    assert not result("Giá trong phạm vi 42.04%")['valid']
    digest["features"][0]["unit"] = "%"
    assert not result("Giá trong phạm vi 39.04%")['valid']


def test_purchase_price_and_horizon_are_allowed_without_hiding_other_numbers():
    digest = {"features": [{"feature_id": "1h_rsi14", "value": 45.0}]}
    answer = {"reasons": [{"feature_ids": ["1h_rsi14"],
                           "text": "giá mua 117840.3 USDT, horizon 360"}]}
    assert verify(answer, digest, purchase_price=117840.3, horizon_minutes=360)["valid"]
    answer["reasons"][0]["text"] = "giá mua 117940.3 USDT, horizon 361"
    issues = verify(answer, digest, purchase_price=117840.3, horizon_minutes=360)["issues"]
    assert {issue["value"] for issue in issues} == {"117940.3", "361"}
