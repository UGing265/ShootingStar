"""Bounded forecast prompt and Gemini response schema."""

import json

PROMPT_VERSION = "forecast-6h-v1"
RESPONSE_SCHEMA = {
    "type": "OBJECT", "required": ["direction", "confidence", "reasons", "risks"],
    "properties": {
        "direction": {"type": "STRING", "enum": ["UP", "DOWN"]},
        "confidence": {"type": "STRING", "enum": ["LOW", "MEDIUM", "HIGH"]},
        "reasons": {"type": "ARRAY", "items": {"type": "OBJECT", "required": ["feature_ids", "text"],
            "properties": {"feature_ids": {"type": "ARRAY", "items": {"type": "STRING"}}, "text": {"type": "STRING"}}}},
        "risks": {"type": "ARRAY", "items": {"type": "STRING"}},
    },
}


def build_prompt(digest, horizon_minutes, purchase_price):
    return (
        "Bạn là nhà nghiên cứu định lượng BTCUSDT. Dự đoán giá tại chân trời "
        f"{horizon_minutes} phút so với giá mua {purchase_price} USDT. "
        "Chỉ dùng dữ liệu digest, không bịa số liệu hoặc sự kiện. Phải chọn UP hoặc DOWN. "
        "Mỗi lý do bằng tiếng Việt, trỏ feature_ids trong digest; chỉ trích số của feature đã trỏ. "
        "HIGH: xu hướng 1h và 4h cùng chiều, được volume hoặc động lượng xác nhận, không có tín hiệu ngược mạnh. "
        "MEDIUM: đa số tín hiệu cùng chiều nhưng có 1–2 tín hiệu ngược. "
        "LOW: tín hiệu trái chiều hoặc không rõ, vẫn chọn hướng nghiêng hơn. "
        "Đưa ra risks và JSON theo schema. Digest:\n" + json.dumps(digest, ensure_ascii=False, separators=(",", ":"))
    )
